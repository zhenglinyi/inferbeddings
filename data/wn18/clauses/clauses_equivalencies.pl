_derivationally_related_form(X0, X1) :- _derivationally_related_form(X1, X0)
_has_part(X0, X1) :- _part_of(X1, X0)
_hypernym(X0, X1) :- _hyponym(X1, X0)
_instance_hypernym(X0, X1) :- _instance_hyponym(X1, X0)
_member_holonym(X0, X1) :- _member_meronym(X1, X0)
_member_of_domain_region(X0, X1) :- _synset_domain_region_of(X1, X0)
_member_of_domain_topic(X0, X1) :- _synset_domain_topic_of(X1, X0)
_member_of_domain_usage(X0, X1) :- _synset_domain_usage_of(X1, X0)
_verb_group(X0, X1) :- _verb_group(X1, X0)
