import lib.summary as summary

import lib.so as so
import lib.meetup as meetup
import lib.github as github
import lib.twitter as twitter
import lib.schema as schema
from lib.config import read_config

import datetime
from datetime import timezone
from dateutil import parser
import json
import os
import boto3



config = read_config()

def constraints(event, _):
    print("Event:", event)

    credentials = config["credentials"]
    write_credentials = credentials["write"]

    neo4j_url = "{url}".format(url=config.get("serverUrl", "bolt+routing://localhost"))
    neo4j_user = write_credentials.get('user', "neo4j")
    neo4j_password = write_credentials['password']

    schema.configure_constraints(neo4j_url=neo4j_url, neo4j_user=neo4j_user, neo4j_pass=neo4j_password)


def generate_page_summary(event, _):
    print("Event:", event)

    url = config["serverUrl"]

    read_only_credentials = config["credentials"]["readonly"]
    user = read_only_credentials["user"]
    password = read_only_credentials["password"]

    title = config["communityName"]
    short_name = config["s3Bucket"]
    logo_src = config["logo"]

    summary.generate(url, user, password, title, short_name, logo_src)


def as_timestamp(dt):
    return int(datetime.datetime.timestamp(dt))


def so_publish_events_import(event, context):
    tag = config["tag"]
    topic_arn = os.environ['STACKOVERFLOW_TOPIC']
    sns = boto3.client('sns')
    start_date = (datetime.datetime.now(timezone.utc) - datetime.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    end_date = datetime.datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    params = {"startDate": start_date, "endDate": end_date, "tags": tag}
    sns.publish(TopicArn=topic_arn, Message=json.dumps(params))

def so_import(event, _):
    print("Event:", event)

    neo4j_url = "{url}".format(url=config.get("serverUrl", "bolt+routing://localhost"))

    credentials = config["credentials"]
    write_credentials = credentials["write"]
    neo4j_user = write_credentials.get('user', "neo4j")
    neo4j_password = write_credentials['password']
    so_key = credentials["stackOverflowApiKey"]

    importer = so.SOImporter(neo4j_url, neo4j_user, neo4j_password, so_key)

    for record in event["Records"]:
        message = json.loads(record["Sns"]["Message"])

        tags = message["tags"]
        start_date = as_timestamp(parser.parse(message["startDate"]))
        end_date = as_timestamp(parser.parse(message["endDate"]))

        importer.process_tag(tags, start_date, end_date)


def meetup_events_import(event, _):
    print("Event:", event)

    credentials = config["credentials"]
    write_credentials = credentials["write"]

    neo4j_url = "{url}".format(url=config.get("serverUrl", "bolt+routing://localhost"))
    neo4j_user = write_credentials.get('user', "neo4j")
    neo4j_password = write_credentials['password']
    meetup_key = credentials["meetupApiKey"]

    meetup.import_events(neo4j_url=neo4j_url, neo4j_user=neo4j_user, neo4j_pass=neo4j_password, meetup_key=meetup_key)


def meetup_groups_import(event, _):
    print("Event:", event)

    credentials = config["credentials"]
    write_credentials = credentials["write"]

    neo4j_url = "{url}".format(url=config.get("serverUrl", "bolt+routing://localhost"))
    neo4j_user = write_credentials.get('user', "neo4j")
    neo4j_password = write_credentials['password']
    meetup_key = credentials["meetupApiKey"]
    tag = config["tag"]

    meetup.import_groups(neo4j_url=neo4j_url, neo4j_user=neo4j_user, neo4j_pass=neo4j_password, tag=tag,
                         meetup_key=meetup_key)


def github_publish_events_import(event, context):
    tag = config["tag"]
    topic_arn = os.environ['GITHUB_TOPIC']
    sns = boto3.client('sns')

    for tags in github.chunker(tag, 5):
        start_date = (datetime.datetime.now(timezone.utc) - datetime.timedelta(hours=1)).strftime(
            "%Y-%m-%dT%H:%M:%S+00:00")
        end_date = datetime.datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
        # maybe I can add a field that indicates if it's an import or release asset downloadCount update
        params = {"startDate": start_date, "endDate": end_date, "tags": tags}
        sns.publish(TopicArn=topic_arn, Message=json.dumps(params))


def github_import(event, _):
    print("Event:", event)

    credentials = config["credentials"]
    write_credentials = credentials["write"]

    neo4j_url = "{url}".format(url=config.get("serverUrl", "bolt+routing://localhost"))
    neo4j_user = write_credentials.get('user', "neo4j")
    neo4j_password = write_credentials['password']
    github_token = credentials["githubToken"]

    importer = github.GitHubImporter(neo4j_url, neo4j_user, neo4j_password, github_token)
    importer.update_release_assets()
    importer.process_tag(["neo4j"],
     (datetime.datetime.now(timezone.utc) - datetime.timedelta(hours=1)).strftime(
            "%Y-%m-%dT%H:%M:%S+00:00"),
             datetime.datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
             )
    #for record in event["Records"]:
    #    message = json.loads(record["Sns"]["Message"])

    #    tags = message["tags"]
    #    start_date = message["startDate"]
    #    end_date = message["endDate"]

    #    importer.process_tag(tags, start_date, end_date)

def twitter_publish_events_import(event, context):
    print("Event:", event)

    credentials = config["credentials"]
    topic_arn = os.environ['TWITTER_TOPIC']

    neo4j_url = "{url}".format(url=config.get("serverUrl", "bolt+routing://localhost"))
    neo4j_user = credentials["readonly"].get('user', "neo4j")
    neo4j_password = credentials["readonly"]['password']

    sns = boto3.client('sns')

    twitter_bearer = credentials["twitterBearer"]
    search = config["twitterSearch"]

    since_id = twitter.find_last_tweet(neo4j_url=neo4j_url, neo4j_user=neo4j_user, neo4j_pass=neo4j_password)
    print(f"Most recent tweet: {since_id}")

    tweets = twitter.find_tweets_since(since_id=since_id, search=search, bearer_token=twitter_bearer)
    count = 0
    for tweet in tweets:
        sns.publish(TopicArn=topic_arn, Message=json.dumps(tweet))
        # print(tweet["id"])
        count = count +1
    print("Found, #" + str(count) + " tweets since")

def twitter_topic_import(event, _):
    print("Event:", event)

    credentials = config["credentials"]
    write_credentials = credentials["write"]

    neo4j_url = "{url}".format(url=config.get("serverUrl", "bolt+routing://localhost"))
    neo4j_user = write_credentials.get('user', "neo4j")
    neo4j_password = write_credentials['password']

    importer = twitter.TwitterImporter(neo4j_url, neo4j_user, neo4j_password)

    for record in event["Records"]:
        tweet = json.loads(record["Sns"]["Message"])
        print(f"Processing tweet {tweet['id']}")

        for url in tweet["entities"]["urls"]:
            initial_uri = url["expanded_url"]
            expanded_uri = importer.unshorten(initial_uri)
            cleaned_uri = importer.clean_uri(expanded_uri)

            print(f"Initial: {initial_uri}, Expanded: {expanded_uri}, Cleaned: {cleaned_uri}")

            url["expanded_url"] = cleaned_uri

            title = importer.hydrate_url(expanded_uri)
            url["title"] = title

        importer.import_tweet(tweet)



def twitter_import(event, _):
    print("Event:", event)

    credentials = config["credentials"]
    write_credentials = credentials["write"]

    neo4j_url = "{url}".format(url=config.get("serverUrl", "bolt+routing://localhost"))
    neo4j_user = write_credentials.get('user', "neo4j")
    neo4j_password = write_credentials['password']

    twitter_bearer = credentials["twitterBearer"]
    search = config["twitterSearch"]

    twitter.import_links(neo4j_url=neo4j_url, neo4j_user=neo4j_user, neo4j_pass=neo4j_password,
                         bearer_token=twitter_bearer, search=search)


def twitter_clean_links(event, _):
    print("Event:", event)

    credentials = config["credentials"]
    write_credentials = credentials["write"]

    neo4j_url = "{url}".format(url=config.get("serverUrl", "bolt+routing://localhost"))
    neo4j_user = write_credentials.get('user', "neo4j")
    neo4j_password = write_credentials['password']

    twitter.clean_links(neo4j_url=neo4j_url, neo4j_user=neo4j_user, neo4j_pass=neo4j_password)


def twitter_hydrate_links(event, _):
    print("Event:", event)

    credentials = config["credentials"]
    write_credentials = credentials["write"]

    neo4j_url = "{url}".format(url=config.get("serverUrl", "bolt+routing://localhost"))
    neo4j_user = write_credentials.get('user', "neo4j")
    neo4j_password = write_credentials['password']

    twitter.hydrate_links(neo4j_url=neo4j_url, neo4j_user=neo4j_user, neo4j_pass=neo4j_password)


def twitter_unshorten_links(event, _):
    print("Event:", event)

    credentials = config["credentials"]
    write_credentials = credentials["write"]

    neo4j_url = "{url}".format(url=config.get("serverUrl", "bolt+routing://localhost"))
    neo4j_user = write_credentials.get('user', "neo4j")
    neo4j_password = write_credentials['password']

    twitter.unshorten_links(neo4j_url=neo4j_url, neo4j_user=neo4j_user, neo4j_pass=neo4j_password)

def summary_page(event,_):
    print("Event: ", event)
    url = config["serverUrl"]

    read_only_credentials = config["credentials"]["readonly"]
    user = read_only_credentials["user"]
    password = read_only_credentials["password"]

    title = config["communityName"]
    logo_src = config["logo"]
    rendered = summary.summarize(url, user, password, title, logo_src)
    response = {
        "statusCode": 200,
        "headers": {
            "Content-Type": "text/html"
        },
        "body": rendered
    }
    return response


