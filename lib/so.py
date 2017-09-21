import time

import requests
from neo4j.v1 import GraphDatabase, basic_auth

import_query = """\
WITH {json} as data
UNWIND data.items as q
MERGE (question:Question:Content:StackOverflow {id:q.question_id})
  ON CREATE SET question.title = q.title, question.url = q.share_link, question.created = q.creation_date
SET question.favorites = q.favorite_count, question.updated = q.last_activity_date, question.views = q.view_count,
    question.upVotes = q.up_vote_count, question.downVotes = q.down_vote_count
FOREACH (q_owner IN [o in [q.owner] WHERE o.user_id IS NOT NULL] |
  MERGE (owner:User:StackOverflow {id:q.owner.user_id}) ON CREATE SET owner.name = q.owner.display_name
  MERGE (owner)-[:POSTED]->(question)
)
FOREACH (tagName IN q.tags | MERGE (tag:Tag{name:tagName}) SET tag:StackOverflow MERGE (question)-[:TAGGED]->(tag))
FOREACH (a IN q.answers |
   MERGE (answer:Answer:Content:StackOverflow {id:a.answer_id})
   SET answer.accepted = a.is_accepted, answer.upVotes = a.up_vote_count, answer.downVotes = a.down_vote_count
   MERGE (question)<-[:ANSWERED]-(answer)
   FOREACH (a_owner IN filter(o IN [a.owner] where o.user_id is not null) |
     MERGE (answerer:User:StackOverflow {id:a_owner.user_id})
     ON CREATE SET answerer.name = a_owner.display_name
     SET answerer.reputation = a_owner.reputation, answerer.profileImage = a_owner.profile_image
     MERGE (answer)<-[:POSTED]-(answerer)
   )
)
"""


def import_so(neo4j_url, neo4j_user, neo4j_pass, tag):
    with GraphDatabase.driver(neo4j_url, auth=basic_auth(neo4j_user, neo4j_pass)) as driver:
        with driver.session() as session:
            page = 1
            items = 100
            has_more = True

            while has_more:
                api_url = "https://api.stackexchange.com/2.2/search?page={page}&pagesize={items}&order=asc&sort=creation&tagged={tag}&site=stackoverflow&filter=!5-i6Zw8Y)4W7vpy91PMYsKM-k9yzEsSC1_Uxlf".format(
                    tag=tag, page=page, items=items)
                print("SO API URL: {url}".format(url=api_url))
                #    if maxDate <> None:
                #        api_url += "&min={maxDate}".format(maxDate=maxDate)

                # Send GET request.
                response = requests.get(api_url, headers={"accept": "application/json"})
                print(response.status_code)
                if response.status_code != 200:
                    print(response.text)
                json = response.json()
                print("has_more", json.get("has_more", False), "quota", json.get("quota_remaining", 0))
                if json.get("items", None) is not None:
                    print(len(json["items"]))
                    result = session.run(import_query, {"json": json})
                    print(result.consume().counters)
                    page = page + 1

                has_more = json.get("has_more", False)
                print("has_more: {more} page {page}".format(page=page, more=has_more))
                if json.get('quota_remaining', 0) <= 0:
                    time.sleep(10)
                if json.get('backoff', None) is not None:
                    print("backoff", json['backoff'])
                    time.sleep(json['backoff'] + 5)
