from datetime import datetime, timezone

import boto
import flask
from ago import human
from flask import render_template
from neo4j.v1 import GraphDatabase

twitter_query = """\
WITH ((timestamp() / 1000) - (7 * 24 * 60 * 60)) AS oneWeekAgo
MATCH (l:Link)<--(t:Tweet:Content)
WHERE not(t:Retweet)

WITH oneWeekAgo, l, t
ORDER BY l.cleanUrl, toInteger(t.created)

WITH oneWeekAgo, l.cleanUrl AS url, l.title AS title, collect(t) AS tweets
WHERE toInteger(tweets[0].created) is not null AND tweets[0].created > oneWeekAgo AND NONE(rogue in ["abizy.com", "twitter.com", "corneey.com"] WHERE url contains rogue)
WITH url, title,
       REDUCE(acc = 0, tweet IN tweets | acc + tweet.favorites + size((tweet)<-[:RETWEETED]-())) AS score,
       tweets[0].created * 1000 AS dateCreated,
       [ tweet IN tweets | head([ (tweet)<-[:POSTED]-(user) | user.screen_name]) ] AS users
RETURN url, title, score, dateCreated, apoc.coll.toSet(users) AS users       
ORDER BY score DESC
"""

github_query = """\
MATCH (n:Repository) WHERE EXISTS(n.created) AND n.pushed > timestamp() - 7 * 60 * 60 * 24 * 1000
WITH n
ORDER BY n.updated desc
MATCH (n)<-[:CREATED]-(user)
RETURN n.title, n.url, n.created, n.favorites, n.updated, user.name, n.created_at, n.updated_at, n.description, n.pushed, n.pushed_at
ORDER BY n.pushed desc
"""

meetup_query = """\
MATCH (event:Event)<-[:CONTAINED]-(group)
WHERE timestamp() + 7 * 60 * 60 * 24 * 1000 > event.time > timestamp() - 7 * 60 * 60 * 24 * 1000
RETURN event, group
ORDER BY event.time
"""

so_query = """\
WITH ((timestamp() / 1000) - (7 * 24 * 60 * 60)) AS oneWeekAgo
match (tag)<-[:TAGGED]-(question:Question:Content:StackOverflow)<--(:Answer)<-[:POSTED]-(user)
WHERE question.created > oneWeekAgo
RETURN question, COLLECT(DISTINCT tag.name) AS tags
ORDER BY question.views DESC
"""

github_active_query = """
MATCH (n:Repository) WHERE EXISTS(n.created) AND n.updated > timestamp() - 7* 60 * 60 * 24 * 1000
WITH n
MATCH (n)<-[:CREATED]-(user) WHERE NOT (user.name IN ["neo4j", "neo4j-contrib"])
WITH user, COUNT(*) AS count, COLLECT(n) as repos
ORDER BY count desc
RETURN user.name, user.avatarUrl, count, [repo in repos | repo { .title, .full_name }] AS repositories
"""

twitter_active_query = """\
MATCH (n:Tweet)
WHERE EXISTS(n.created) AND n.created > ((timestamp() / 1000) - 7 * 60 * 60 * 24 )
WITH n
MATCH (n)<-[:POSTED]-(user) WHERE NOT (user.screen_name IN ["neo4j", "neo4j-contrib"])

WITH user, COUNT(*) AS count
ORDER BY count desc
WITH user, count, [70,63,56,49,42,35,28,21,14,7,0] AS previousWeeks

WITH user, count,
    [daysAgo in previousWeeks | size([path in (user)-[:POSTED]->(:Tweet) WHERE EXISTS(nodes(path)[-1].created)
AND ((timestamp() / 1000) - daysAgo * 60 * 60 * 24 ) > nodes(path)[-1].created > ((timestamp() / 1000) - (daysAgo+7) * 60 * 60 * 24 )])] AS lastWeekCount

RETURN user.screen_name AS user, count, lastWeekCount
ORDER BY count desc
"""

so_active_query = """\
WITH ((timestamp() / 1000) - (7 * 24 * 60 * 60)) AS oneWeekAgo,
     ((timestamp() / 1000) - (14* 24 * 60 * 60)) AS twoWeeksAgo
MATCH (question:Question:Content:StackOverflow)<--(:Answer)<-[:POSTED]-(user)
WHERE question.created > oneWeekAgo

WITH user, count(*) AS replies, oneWeekAgo, twoWeeksAgo
ORDER BY replies DESC
OPTIONAL MATCH (user)-[:POSTED]->(:Answer)-->(question:Question)
WHERE oneWeekAgo > question.created > twoWeeksAgo
RETURN user, replies, COUNT(question) AS lastWeekReplies
ORDER BY replies DESC
"""

app = flask.Flask('my app')


@app.template_filter('humanise')
def humanise_filter(value):
    return human(datetime.fromtimestamp(value / 1000), precision=1)


@app.template_filter("shorten")
def shorten_filter(value):
    if not value:
        return value
    else:
        return (value[:75] + '..') if len(value) > 75 else value


@app.template_filter('stringseparate')
def string_separate_filter(value):
    return ",".join(str(i) for i in value)


def generate(url, user, password, title, short_name, logo_src):
    with GraphDatabase.driver("bolt://{url}".format(url=url), auth=(user, password)) as driver:
        with driver.session() as session:
            github_records = session.read_transaction(lambda tx: list(tx.run(github_query)))
            twitter_records = session.read_transaction(lambda tx: list(tx.run(twitter_query)))
            meetup_records = session.read_transaction(lambda tx: list(tx.run(meetup_query)))
            so_records = session.read_transaction(lambda tx: list(tx.run(so_query)))
            github_active_members = session.read_transaction(lambda tx: list(tx.run(github_active_query)))
            twitter_active_members = session.read_transaction(lambda tx: list(tx.run(twitter_active_query)))
            so_active_members = session.read_transaction(lambda tx: list(tx.run(so_active_query)))

    with app.app_context():
        rendered = render_template('index.html',
                                   github_records=github_records,
                                   twitter_records=twitter_records,
                                   meetup_records=meetup_records,
                                   so_records=so_records,
                                   github_active_members=github_active_members,
                                   twitter_active_members=twitter_active_members,
                                   so_active_members=so_active_members,
                                   title=title,
                                   logo_src=logo_src,
                                   time_now=str(datetime.now(timezone.utc)))

        local_file_name = "/tmp/{file_name}.html".format(file_name=short_name)
        with open(local_file_name, "wb") as file:
            file.write(rendered.encode('utf-8'))

        s3_connection = boto.connect_s3()
        bucket = s3_connection.get_bucket(short_name)
        key = boto.s3.key.Key(bucket, "{summary}.html".format(summary=short_name))
        key.set_contents_from_filename(local_file_name)
