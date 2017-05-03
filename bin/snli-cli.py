#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import os
import sys

import numpy as np
import tensorflow as tf

import tensorflow.contrib.keras as keras

from inferbeddings.models.training.util import make_batches
from inferbeddings.rte import ConditionalBiLSTM
from inferbeddings.rte.util import SNLI, pad_sequences, count_parameters

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
logger = logging.getLogger(os.path.basename(sys.argv[0]))


def to_feed_dict(model, dataset):
    return {
        model.sentence1: dataset.sentences1, model.sentence2: dataset.sentences2,
        model.sentence1_size: dataset.sizes1, model.sentence2_size: dataset.sizes2,
        model.label: dataset.labels}


def to_dataset(corpus, max_len=None):
    q, qlen = corpus['question'], corpus['question_lengths']
    s, slen = corpus['support'], corpus['support_lengths'],
    return {
        'questions': pad_sequences(q, max_len=max_len),
        'sentences': pad_sequences([_s for [_s] in s], max_len=max_len),
        'question_lengths': np.clip(a=np.array(qlen), a_min=0, a_max=max_len),
        'sentence_lengths': np.clip(a=np.array(slen)[:, 0], a_min=0, a_max=max_len),
        'answers': corpus['answers']}


def train_tokenizer_on_instances(instances, num_words=None):
    question_texts = [instance['question'] for instance in instances]
    support_texts = [instance['support'] for instance in instances]
    answer_texts = [instance['answer'] for instance in instances]

    qs_tokenizer, a_tokenizer = keras.preprocessing.text.Tokenizer(num_words=num_words), keras.preprocessing.text.Tokenizer()

    qs_tokenizer.fit_on_texts(question_texts + support_texts)
    a_tokenizer.fit_on_texts(answer_texts)

    return qs_tokenizer, a_tokenizer


def to_corpus(instances, qs_tokenizer, a_tokenizer):
    question_texts = [instance['question'] for instance in instances]
    support_texts = [instance['support'] for instance in instances]
    answer_texts = [instance['answer'] for instance in instances]
    assert qs_tokenizer is not None and a_tokenizer is not None
    corpus = {
        'question': qs_tokenizer.texts_to_sequences(question_texts),
        'support': [[s] for s in qs_tokenizer.texts_to_sequences(support_texts)],
        'candidates': [0, 1, 2] * len(question_texts),
        'answers': [a - 1 for [a] in a_tokenizer.texts_to_sequences(answer_texts)]}
    assert {a for a in corpus['answers']} == {0, 1, 2}
    # Note - those parts feel redundant
    corpus['question_lengths'] = [len(q) for q in corpus['question']]
    corpus['support_lengths'] = [[len(s)] for [s] in corpus['support']]
    corpus['ids'] = list(range(len(corpus['question'])))
    return corpus


def main(argv):
    logger.debug('Reading corpus ..')

    train, dev, test = SNLI.generate(
        # train_path='data/snli/snli_1.0_dev.jsonl.gz',
        # dev_path='data/snli/snli_1.0_dev.jsonl.gz',
        # test_path='data/snli/snli_1.0_dev.jsonl.gz'
    )

    logger.debug('Parsing corpus ..')

    num_words = None
    qs_tokenizer, a_tokenizer = train_tokenizer_on_instances(train + dev + test, num_words=num_words)

    train_corpus = to_corpus(train, qs_tokenizer, a_tokenizer)
    dev_corpus = to_corpus(dev, qs_tokenizer, a_tokenizer)
    test_corpus = to_corpus(test, qs_tokenizer, a_tokenizer)

    vocab_size = qs_tokenizer.num_words if qs_tokenizer.num_words else len(qs_tokenizer.word_index) + 1

    embedding_size = 300
    batch_size = 1024
    num_units = 300
    nb_epochs = 10000
    dropout_keep_prob = 1.0
    max_len = None

    optimizer = tf.train.AdamOptimizer(learning_rate=0.001)

    logger.info('Train size: {}\tDev size: {}\tTest size: {}'
                .format(len(train_corpus['question']), len(dev_corpus['question']), len(test_corpus['question'])))

    train_dataset = to_dataset(train_corpus, max_len=max_len)
    dev_dataset, test_dataset = to_dataset(dev_corpus, max_len=max_len), to_dataset(test_corpus, max_len=max_len)

    questions, sentences = train_dataset['questions'], train_dataset['sentences']
    question_lengths, sentence_lengths = train_dataset['question_lengths'], train_dataset['sentence_lengths']
    answers = train_dataset['answers']

    model = ConditionalBiLSTM(optimizer=optimizer, num_units=num_units, num_classes=3,
                              vocab_size=vocab_size, embedding_size=embedding_size,
                              dropout_keep_prob=dropout_keep_prob, l2_lambda=1e-5)

    word_idx_ph = tf.placeholder(dtype=tf.int32, name='word_idx')
    word_embedding_ph = tf.placeholder(dtype=tf.float32, shape=[None], name='word_embedding')
    assign_word_embedding = model.embeddings[word_idx_ph, :].assign(word_embedding_ph)

    correct_predictions = tf.equal(tf.cast(model.predictions, tf.int32), tf.cast(model.label, tf.int32))
    accuracy = tf.reduce_mean(tf.cast(correct_predictions, tf.float32))

    init_op = tf.global_variables_initializer()

    session_config = tf.ConfigProto()
    session_config.gpu_options.allow_growth = True

    with tf.Session(config=session_config) as session:
        session.run(init_op)
        logger.debug('Total parameters: {}'.format(count_parameters()))

        glove_path = os.path.expanduser('~/data/glove/glove.840B.300d.txt')
        if embedding_size == 300 and os.path.isfile(glove_path):
            from derte.io.embeddings import load_glove
            logger.info('Initialising the embeddings with GloVe vectors ..')

            word_set = {w for w, w_idx in qs_tokenizer.word_index.items()
                        if w_idx < vocab_size}
            with open(glove_path, 'r') as stream:
                word_to_embedding = load_glove(stream=stream, words=word_set)

            for word in word_to_embedding:
                word_idx, word_embedding = qs_tokenizer.word_index[word], word_to_embedding[word]
                session.run(assign_word_embedding, feed_dict={word_idx_ph: word_idx, word_embedding_ph: word_embedding})

            logger.info('Done!')

        random_state = np.random.RandomState(0)

        nb_instances = questions.shape[0]
        batches = make_batches(size=nb_instances, batch_size=batch_size)

        for epoch in range(1, nb_epochs + 1):
            order = random_state.permutation(nb_instances)

            sentences1, sentences2 = questions[order], sentences[order]
            sizes1, sizes2 = question_lengths[order], sentence_lengths[order]
            labels = answers[order]

            loss_values, correct_predictions_values = [], []

            for i, (batch_start, batch_end) in enumerate(batches):
                batch_sentences1, batch_sentences2 = sentences1[batch_start:batch_end], sentences2[batch_start:batch_end]
                batch_sizes1, batch_sizes2 = sizes1[batch_start:batch_end], sizes2[batch_start:batch_end]
                batch_labels = labels[batch_start:batch_end]

                batch_feed_dict = {
                    model.sentence1: batch_sentences1, model.sentence2: batch_sentences2,
                    model.sentence1_size: batch_sizes1, model.sentence2_size: batch_sizes2,
                    model.label: batch_labels}

                _, loss_value, correct_predictions_value =\
                    session.run([model.training_step, model.loss, correct_predictions], feed_dict=batch_feed_dict)

                loss_values += loss_value.tolist()
                correct_predictions_values += correct_predictions_value.tolist()

                if (i > 0 and i % 100 == 0) or (batch_start, batch_end) in batches[-1:]:
                    train_accuracy = np.mean(correct_predictions_values)
                    dev_accuracy = session.run(accuracy, feed_dict=to_feed_dict(model, dev_dataset))
                    test_accuracy = session.run(accuracy, feed_dict=to_feed_dict(model, test_dataset))

                    logger.debug('Epoch {0}/{1}\tTrain Accuracy: {2:.2f}\tDev Accuracy: {3:.2f}\tTest Accuracy: {4:.2f}'
                                 .format(epoch, i, train_accuracy * 100, dev_accuracy * 100, test_accuracy * 100))

            def stats(values):
                return '{0:.4f} ± {1:.4f}'.format(round(np.mean(values), 4), round(np.std(values), 4))

            logger.info('Epoch {}\tLoss: {}'.format(epoch, stats(loss_values)))


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    main(sys.argv[1:])
