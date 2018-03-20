import lib.summary as summary
import lib.so as so
import lib.meetup as meetup
import lib.github as github
import lib.twitter as twitter
import lib.schema as schema

import datetime
from datetime import timezone
from dateutil import parser

from lib.encryption import decrypt_value

import json
import os

import boto3

def read_config():
    config_file = os.getenv('CONFIG_FILE', 'communitygraph.json')
    print("Reading config from {config_file}".format(config_file=config_file))
    with open(config_file) as data_file:
        return json.load(data_file)


config = read_config()

def constraints(event, _):
    print("Event:", event)

    credentials = config["credentials"]
    write_credentials = credentials["write"]

    neo4j_url = "bolt://{url}".format(url=config.get("serverUrl", "localhost"))
    neo4j_user = write_credentials.get('user', "neo4j")
    neo4j_password = decrypt_value(write_credentials['password'])

    schema.configure_constraints(neo4j_url=neo4j_url, neo4j_user=neo4j_user, neo4j_pass=neo4j_password)


def generate_page_summary(event, _):
    print("Event:", event)

    url = config["serverUrl"]

    read_only_credentials = config["credentials"]["readonly"]
    user = read_only_credentials["user"]
    password = decrypt_value(read_only_credentials["password"])

    title = config["communityName"]
    short_name = config["s3Bucket"]
    logo_src = config["logo"]

    summary.generate(url, user, password, title, short_name, logo_src)

def as_timestamp(dt):
    return int(datetime.datetime.timestamp(dt))

def so_publish_events_import(event, context):
    tag = config["tag"]

    context_parts = context.invoked_function_arn.split(':')
    topic_name = "StackOverflow-{0}".format(config["communityName"])
    topic_arn = "arn:aws:sns:{region}:{account_id}:{topic}".format(region=context_parts[3], account_id=context_parts[4], topic=topic_name)

    sns = boto3.client('sns')

    start_date = (datetime.datetime.now(timezone.utc) - datetime.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    end_date = datetime.datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")

    params = {"startDate": start_date, "endDate": end_date, "tags": tag}
    sns.publish(TopicArn= topic_arn, Message= json.dumps(params))

def so_import(event, _):
    print("Event:", event)

    neo4j_url = "bolt://{url}".format(url=config.get("serverUrl", "localhost"))

    credentials = config["credentials"]
    write_credentials = credentials["write"]
    neo4j_user = write_credentials.get('user', "neo4j")
    neo4j_password = decrypt_value(write_credentials['password'])
    so_key = decrypt_value(credentials["stackOverflowApiKey"])

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

    neo4j_url = "bolt://{url}".format(url=config.get("serverUrl", "localhost"))
    neo4j_user = write_credentials.get('user', "neo4j")
    neo4j_password = decrypt_value(write_credentials['password'])
    meetup_key = decrypt_value(credentials["meetupApiKey"])

    meetup.import_events(neo4j_url=neo4j_url, neo4j_user=neo4j_user, neo4j_pass=neo4j_password, meetup_key=meetup_key)


def meetup_groups_import(event, _):
    print("Event:", event)

    credentials = config["credentials"]
    write_credentials = credentials["write"]

    neo4j_url = "bolt://{url}".format(url=config.get("serverUrl", "localhost"))
    neo4j_user = write_credentials.get('user', "neo4j")
    neo4j_password = decrypt_value(write_credentials['password'])
    meetup_key = decrypt_value(credentials["meetupApiKey"])
    tag = config["tag"]

    meetup.import_groups(neo4j_url=neo4j_url, neo4j_user=neo4j_user, neo4j_pass=neo4j_password, tag=tag,
                         meetup_key=meetup_key)


def github_publish_events_import(event, context):
    tag = config["tag"]

    context_parts = context.invoked_function_arn.split(':')
    topic_name = "GitHub-{0}".format(config["communityName"])
    topic_arn = "arn:aws:sns:{region}:{account_id}:{topic}".format(region=context_parts[3], account_id=context_parts[4], topic=topic_name)

    sns = boto3.client('sns')

    for tags in github.chunker(tag, 5):
        start_date = (datetime.datetime.now(timezone.utc) - datetime.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
        end_date = datetime.datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")

        # maybe I can add a field that indicates if it's an import or release asset downloadCount update
        params = {"startDate": start_date, "endDate": end_date, "tags": tags}

        sns.publish(TopicArn=topic_arn, Message=json.dumps(params))


def github_import(event, _):
    print("Event:", event)

    credentials = config["credentials"]
    write_credentials = credentials["write"]

    neo4j_url = "bolt://{url}".format(url=config.get("serverUrl", "localhost"))
    neo4j_user = write_credentials.get('user', "neo4j")
    neo4j_password = decrypt_value(write_credentials['password'])
    github_token = decrypt_value(credentials["githubToken"])

    importer = github.GitHubImporter(neo4j_url, neo4j_user, neo4j_password, github_token)
    importer.update_release_assets()

    for record in event["Records"]:
        message = json.loads(record["Sns"]["Message"])

        tags = message["tags"]
        start_date = message["startDate"]
        end_date = message["endDate"]

        importer.process_tag(tags, start_date, end_date)


def twitter_import(event, _):
    print("Event:", event)

    credentials = config["credentials"]
    write_credentials = credentials["write"]

    neo4j_url = "bolt://{url}".format(url=config.get("serverUrl", "localhost"))
    neo4j_user = write_credentials.get('user', "neo4j")
    neo4j_password = decrypt_value(write_credentials['password'])

    twitter_bearer = decrypt_value(credentials["twitterBearer"])
    search = config["twitterSearch"]

    twitter.import_links(neo4j_url=neo4j_url, neo4j_user=neo4j_user, neo4j_pass=neo4j_password,
                         bearer_token=twitter_bearer, search=search)


def twitter_clean_links(event, _):
    print("Event:", event)

    credentials = config["credentials"]
    write_credentials = credentials["write"]

    neo4j_url = "bolt://{url}".format(url=config.get("serverUrl", "localhost"))
    neo4j_user = write_credentials.get('user', "neo4j")
    neo4j_password = decrypt_value(write_credentials['password'])

    twitter.clean_links(neo4j_url=neo4j_url, neo4j_user=neo4j_user, neo4j_pass=neo4j_password)


def twitter_hydrate_links(event, _):
    print("Event:", event)

    credentials = config["credentials"]
    write_credentials = credentials["write"]

    neo4j_url = "bolt://{url}".format(url=config.get("serverUrl", "localhost"))
    neo4j_user = write_credentials.get('user', "neo4j")
    neo4j_password = decrypt_value(write_credentials['password'])

    twitter.hydrate_links(neo4j_url=neo4j_url, neo4j_user=neo4j_user, neo4j_pass=neo4j_password)


def twitter_unshorten_links(event, _):
    print("Event:", event)

    credentials = config["credentials"]
    write_credentials = credentials["write"]

    neo4j_url = "bolt://{url}".format(url=config.get("serverUrl", "localhost"))
    neo4j_user = write_credentials.get('user', "neo4j")
    neo4j_password = decrypt_value(write_credentials['password'])

    twitter.unshorten_links(neo4j_url=neo4j_url, neo4j_user=neo4j_user, neo4j_pass=neo4j_password)
