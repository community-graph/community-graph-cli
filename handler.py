import lib.summary as summary
import lib.so as so
import lib.meetup as meetup
import lib.github as github
import lib.twitter as twitter

from lib.encryption import decrypt_value

import json


def read_config():
    with open('communitygraph.json') as data_file:
        config = json.load(data_file)
    return config


config = read_config()


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


def so_import(event, _):
    print("Event:", event)

    neo4j_url = "bolt://{url}".format(url=config.get("serverUrl", "localhost"))

    write_credentials = config["credentials"]["write"]
    neo4j_user = write_credentials.get('user', "neo4j")
    neo4j_password = decrypt_value(write_credentials['password'])

    tag = config["tag"]

    so.import_so(neo4j_url=neo4j_url, neo4j_user=neo4j_user, neo4j_pass=neo4j_password, tag=tag)


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


def github_import(event, _):
    print("Event:", event)

    credentials = config["credentials"]
    write_credentials = credentials["write"]

    neo4j_url = "bolt://{url}".format(url=config.get("serverUrl", "localhost"))
    neo4j_user = write_credentials.get('user', "neo4j")
    neo4j_password = decrypt_value(write_credentials['password'])
    github_token = decrypt_value(credentials["githubToken"])
    tag = config["tag"]

    github.import_github(neo4j_url=neo4j_url, neo4j_user=neo4j_user, neo4j_pass=neo4j_password, tag=tag,
                         github_token=github_token)


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
