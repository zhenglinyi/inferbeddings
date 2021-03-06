# YAGO3, mte10

## Download the data:

```bash
$ wget -c http://resources.mpi-inf.mpg.de/yago-naga/yago/download/yago/yagoFacts.tsv.7z
--2017-02-14 15:57:32--  http://resources.mpi-inf.mpg.de/yago-naga/yago/download/yago/yagoFacts.tsv.7z
Resolving resources.mpi-inf.mpg.de (resources.mpi-inf.mpg.de)... 139.19.86.89
Connecting to resources.mpi-inf.mpg.de (resources.mpi-inf.mpg.de)|139.19.86.89|:80... connected.
HTTP request sent, awaiting response... 200 OK
Length: 103497683 (99M) [text/tab-separated-values]
Saving to: ‘yagoFacts.tsv.7z’

yagoFacts.tsv.7z                   100%[================================================================>]  98.70M   476KB/s    in 3m 38s  

2017-02-14 16:01:10 (464 KB/s) - ‘yagoFacts.tsv.7z’ saved [103497683/103497683]
$ md5sum yagoFacts.tsv.7z 
5775c0d55750025c0579160e303ca507  yagoFacts.tsv.7z
```

Enforcing the mte10 limit:

```bash
$ mkdir tmp ; cd tmp
$ 7z e ../yagoFacts.tsv.7z
[..]
$ md5sum yagoFacts.tsv 
d8c1c5f0cca49e91a5706b6fd608a9fd  yagoFacts.tsv
$ gzip -9 yagoFacts.tsv
```

Create a TSV file containing all triples:

```bash
$ cd ..
$ zcat tmp/yagoFacts.tsv.gz | tail -n +2 | awk 'BEGIN {FS="\t"} ; { print $2 "\t" $3 "\t" $4 }' | tr -d '>' | tr -d '<' > yago3.tsv
$ gzip -9 yago3.tsv 
```

Create a list of all entities occurring at least 10 times:

```bash
$ mkdir stats
$ zcat yago3.tsv.gz | awk '{ print $1 "\n" $3 }' | sort | uniq -c | awk '{if ($1 >= 10) {print $2}}' > stats/yago3_entities_mte10.txt
$ md5sum stats/yago3_entities_mte10.txt 
bf0c354499dcbb40f8c22cf214691b66  stats/yago3_entities_mte10.txt
```

Create the mte10-filtered variant:

```bash
$ ./tools/filter.py yago3.tsv.gz stats/yago3_entities_mte10.txt > yago3_mte10.tsv
INFO:root:Acquiring yago3.tsv.gz ..
$ md5sum yago3_mte10.tsv
4e012a562f1088289ddb35316b30896e  yago3_mte10.tsv
$ gzip -9 yago3_mte10.tsv
```

Split yago3_mte10 into validation, training and test sets:

```bash
$ ./tools/split.py yago3_mte10.tsv.gz --train yago3_mte10-train.tsv --valid yago3_mte10-valid.tsv --valid-size 5000 --test yago3_mte10-test.tsv --test-size 5000 --seed 0
DEBUG:root:Importing the Knowledge Graph ..
1089040it [00:04, 267277.10it/s]
DEBUG:root:Number of triples in the Knowledge Graph: 1089040
DEBUG:root:Generating a random permutation of RDF triples ..
DEBUG:root:Building the training, validation and test sets ..
DEBUG:root:Saving ..
$ md5sum *.tsv
14bf97890b2fee774dbce5f326acd189  yago3_mte10-test.tsv
a9da8f583ec3920570eeccf07199229a  yago3_mte10-train.tsv
2d679a906f2b1ac29d74d5c948c1ad09  yago3_mte10-valid.tsv
$ wc -l *.tsv
    5000 yago3_mte10-test.tsv
 1079040 yago3_mte10-train.tsv
    5000 yago3_mte10-valid.tsv
 1089040 total
```
