from neo4j.v1 import GraphDatabase, basic_auth
from future.utils import viewvalues

import dedupe
import csv
import os

query = """\
match (link:Link)
where exists(link.cleanUrl)
return link.title AS title, link.cleanUrl AS uri, id(link) as internalNodeId
order by id(link) desc
"""

data = {}

with GraphDatabase.driver("bolt://138.197.15.1/", auth=basic_auth("all", "readonly")) as driver:
    with driver.session() as session:
        for index, row in enumerate(session.run(query)):
            title = None if row["title"] == '' else row["title"]
            data[index] = {"title": title, "uri": row["uri"], "internalNodeId": row["internalNodeId"]}

# These two generators will give us the corpora setting up the Set
# distance metrics

def uris(data):
    for record in viewvalues(data):
        yield record['uris']


def titles(data):
    for record in viewvalues(data):
        yield record['title']


settings_file = 'data/links_settings.json'
training_file = 'data/links_training.json'
output_file = 'data/links_output.csv'

if os.path.exists(settings_file):
    print('reading from', settings_file)
    with open(settings_file, 'rb') as sf:
        deduper = dedupe.StaticDedupe(sf, num_cores=2)
else:
    fields = [
        {'field': 'title',
         'variable name': 'title',
         'type': 'String',
         'has missing': True},
        {'field': 'uri',
         'type': 'String',
         'corpus': uris(data),
         'has missing': False},
        {'field': 'title',
         'variable name': 'titleText',
         'type': 'Text',
         'corpus': titles(data),
         'has missing': True},
        {'type': 'Interaction',
         'interaction variables': ['title', 'titleText']}
    ]

    deduper = dedupe.Dedupe(fields, num_cores=2)

    deduper.sample(data, 100000)

    if os.path.exists(training_file):
        print('reading labeled examples from ', training_file)
        with open(training_file) as tf:
            deduper.readTraining(tf)

print('starting active labeling...')
dedupe.consoleLabel(deduper)

deduper.train()

# When finished, save our training away to disk
with open(training_file, 'w') as tf:
    deduper.writeTraining(tf)

# Save our weights and predicates to disk.  If the settings file
# exists, we will skip all the training and learning next time we run
# this file.
with open(settings_file, 'wb') as sf:
    deduper.writeSettings(sf)

clustered_dupes = deduper.match(data, 0.2)

cluster_membership = {}
cluster_id = 0
for cluster_id, (cluster, scores) in enumerate(clustered_dupes):
    for record_id, score in zip(cluster, scores):
        cluster_membership[record_id] = (cluster_id, score)

unique_id = cluster_id + 1

with open(output_file, 'w') as f_out:
    writer = csv.writer(f_out)

    writer.writerow(["clusterId", "score", "internalNodeId", "title", "uri"])

    for index in data:
        if index in cluster_membership:
            cluster_id, score = cluster_membership[index]
        else:
            cluster_id, score = unique_id, None
            unique_id += 1

        row = data[index]

        writer.writerow([cluster_id, score, row["internalNodeId"], row["title"], row["uri"]])
