import csv
from collections import Counter
import flask
from flask import Flask, render_template, request, redirect, url_for
from neo4j.v1 import GraphDatabase, basic_auth

app = Flask(__name__)
driver = GraphDatabase.driver("bolt://138.197.15.1/", auth=basic_auth("neo4j", "RUXePcMaDimWNpmFgt4iHXMa"))

dedupe_clusters = {}
dedupe_clusters_links = {}
counter = Counter()

with open("data/links_output.csv", "r") as output_file:
    reader = csv.reader(output_file, delimiter = ",")

    next(reader)

    for row in reader:
        counter[row[0]] += 1

        if not dedupe_clusters.get(row[0]):
            dedupe_clusters[row[0]] = []
            dedupe_clusters_links[row[0]] = set()
        dedupe_clusters[row[0]].append( {"uri": row[4], "internalNodeId": row[2] } )
        dedupe_clusters_links[row[0]].add(row[4])


@app.route("/")
def clusters():
    return render_template("clusters.html", clusters = dedupe_clusters_links, counter = counter)

merge_query = """\
WITH [id in {ids} | toInteger(id)] AS ids
MATCH (n:Link)<--(t:Tweet:Content)
where id(n) in ids
WITH n, t.favorites + size((t)<-[:RETWEETED]-()) AS score, ids
ORDER BY score DESC
LIMIT 1
WITH n, ids

CALL apoc.periodic.iterate(
  "MATCH (n) WHERE id(n) in {ids} AND id(n) <> {nodeId} RETURN n",
  "MATCH (other) WHERE id(other) = {nodeId}
   MATCH (n)
   call apoc.refactor.mergeNodes([other, n])
   yield node
   return count(*)",
   { batchSize:1, parallel:false, params: {nodeId: id(n), ids: ids}})
yield batches, total, timeTaken, committedOperations, failedOperations, failedBatches, retries, errorMessages, batch, operations
return *
"""

@app.route("/clusters/<cluster_id>", methods=["POST"])
def merge_cluster(cluster_id):
    params = {
        "ids": [int(item["internalNodeId"]) for item in dedupe_clusters[cluster_id]]
    }
    print(params)

    with driver.session() as session:
        result = session.run(merge_query, params)
        print(result)

    return redirect(url_for('clusters'))