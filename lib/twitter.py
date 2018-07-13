import socket
import time
import urllib
import urllib.parse
from urllib.parse import urlencode, urlparse, urlunparse, parse_qs
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from neo4j.v1 import GraphDatabase, basic_auth
from user_agent import generate_user_agent, generate_navigator

# from neo4j.util import Watcher
# watcher = Watcher("neo4j.bolt")
# watcher.watch()

import_tweet_query = """\
WITH {tweet} AS t

WITH t,
     t.entities AS e,
     t.user AS u,
     t.retweeted_status AS retweet

MERGE (tweet:Tweet:Twitter {id:t.id})
SET tweet:Content, tweet.text = t.text,
    tweet.created_at = t.created_at,
    tweet.created = apoc.date.parse(t.created_at,'s','E MMM dd HH:mm:ss Z yyyy'),
    tweet.favorites = t.favorite_count

MERGE (user:User {screen_name:u.screen_name})
SET user.name = u.name, user.id = u.id,
    user.location = u.location,
    user.followers = u.followers_count,
    user.following = u.friends_count,
    user.statuses = u.statuses_count,
    user.profile_image_url = u.profile_image_url,
    user:Twitter

MERGE (user)-[:POSTED]->(tweet)

FOREACH (h IN e.hashtags |
  MERGE (tag:Tag {name:LOWER(h.text)}) SET tag:Twitter
  MERGE (tag)<-[:TAGGED]-(tweet)
)

FOREACH (u IN e.urls |
  MERGE (url:Link {url:u.expanded_url})
  SET url:Twitter, url.title = u.title, url.l.cleanUrl = u.expanded_url
  MERGE (tweet)-[:LINKED]->(url)
)

FOREACH (m IN e.user_mentions |
  MERGE (mentioned:User {screen_name:m.screen_name})
  ON CREATE SET mentioned.name = m.name, mentioned.id = m.id
  SET mentioned:Twitter
  MERGE (tweet)-[:MENTIONED]->(mentioned)
)

FOREACH (r IN [r IN [t.in_reply_to_status_id] WHERE r IS NOT NULL] |
  MERGE (reply_tweet:Tweet:Twitter {id:r})
  MERGE (tweet)-[:REPLIED_TO]->(reply_tweet)
  SET tweet:Reply
)

FOREACH (retweet_id IN [x IN [retweet.id] WHERE x IS NOT NULL] |
    MERGE (retweet_tweet:Tweet:Twitter {id:retweet_id})
    MERGE (tweet)-[:RETWEETED]->(retweet_tweet)
    SET tweet:Retweet
)
"""

class TwitterImporter:
    def __init__(self, neo4j_url, neo4j_user, neo4j_pass):
        self.neo4j_url = neo4j_url
        self.neo4j_user = neo4j_user
        self.neo4j_pass = neo4j_pass

    def import_tweet(self, tweet):
        print(f"importing... {tweet}")

        with GraphDatabase.driver(self.neo4j_url, auth=basic_auth(self.neo4j_user, self.neo4j_pass)) as driver:
            with driver.session() as session:
                result = session.run(import_tweet_query, {"tweet": tweet})
                print(result.consume().counters)
                print("importing that tweet")

    def unshorten(self, url):
        session = requests.Session()  # so connections are recycled
        resp = session.head(url, allow_redirects=True)
        return resp.url

    def clean_uri(self, url):
        url = url.encode('utf-8')
        u = urlparse(url)
        query = parse_qs(u.query.decode("utf-8"))

        for param in ["utm_content", "utm_source", "utm_medium", "utm_campaign", "utm_term"]:
            query.pop(param, None)

        u = u._replace(query=bytes(urlencode(query, True), "utf-8"))

        return urlunparse(u).decode("utf-8")

    def hydrate_url(self, url):
        user_agent = {'User-agent': generate_user_agent()}
        potential_title = []
        try:
            if url:
                r = requests.get(url, headers=user_agent, timeout=5.0)
                response = r.text
                page = BeautifulSoup(response, "html.parser")
                potential_title = page.find_all("title")
        except requests.exceptions.ConnectionError:
            print("Failed to connect: ", url)
        except requests.exceptions.ReadTimeout:
            print("Read timed out: ", url)

        if len(potential_title) == 0:
            print("Skipping: ", url)
            return "N/A"
        else:
            return potential_title[0].text


find_short_links_query = """\
MATCH (link:Link)
WHERE exists(link.short) OR link.url contains "r.neo4j.com"
RETURN id(link) as id, link.url as url
ORDER BY id DESC
LIMIT {limit}
"""

unshorten_query = """\
UNWIND {data} AS row
MATCH (link)
WHERE id(link) = row.id
SET link.url = row.url
REMOVE link.short
"""


def unshorten_links(neo4j_url, neo4j_user, neo4j_pass):
    with GraphDatabase.driver(neo4j_url, auth=basic_auth(neo4j_user, neo4j_pass)) as driver:
        with driver.session() as session:
            result = session.run(find_short_links_query, {"limit": 100})
            update = []
            rows = 0
            for record in result:
                try:
                    resolved = unshorten_url(record["url"])
                    print("original", record["url"], "resolved", resolved)
                    rows = rows + 1
                    update += [{"id": record["id"], "url": resolved}]
                except AttributeError:
                    print("Failed to resolve {0}. Ignoring for now".format(record["url"]))
                except socket.gaierror:
                    print("Failed to resolve {0}. Ignoring for now".format(record["url"]))
                except socket.error:
                    print("Failed to connect to {0}. Ignoring for now".format(record["url"]))

            print("urls", len(update), "records", rows)
            result = session.run(unshorten_query, {"data": update})
            print(result.consume().counters)

import_query = """\
UNWIND {tweets} AS t

WITH t
ORDER BY t.id

WITH t,
     t.entities AS e,
     t.user AS u,
     t.retweeted_status AS retweet

MERGE (tweet:Tweet:Twitter {id:t.id})
SET tweet:Content, tweet.text = t.text,
    tweet.created_at = t.created_at,
    tweet.created = apoc.date.parse(t.created_at,'s','E MMM dd HH:mm:ss Z yyyy'),
    tweet.favorites = t.favorite_count

MERGE (user:User {screen_name:u.screen_name})
SET user.name = u.name, user.id = u.id,
    user.location = u.location,
    user.followers = u.followers_count,
    user.following = u.friends_count,
    user.statuses = u.statuses_count,
    user.profile_image_url = u.profile_image_url,
    user:Twitter

MERGE (user)-[:POSTED]->(tweet)

FOREACH (h IN e.hashtags |
  MERGE (tag:Tag {name:LOWER(h.text)}) SET tag:Twitter
  MERGE (tag)<-[:TAGGED]-(tweet)
)

FOREACH (u IN e.urls |
  MERGE (url:Link {url:u.expanded_url})
  ON CREATE SET url.short = case when length(u.expanded_url) < 25 then true else null end
  SET url:Twitter
  MERGE (tweet)-[:LINKED]->(url)
)

FOREACH (m IN e.user_mentions |
  MERGE (mentioned:User {screen_name:m.screen_name})
  ON CREATE SET mentioned.name = m.name, mentioned.id = m.id
  SET mentioned:Twitter
  MERGE (tweet)-[:MENTIONED]->(mentioned)
)

FOREACH (r IN [r IN [t.in_reply_to_status_id] WHERE r IS NOT NULL] |
  MERGE (reply_tweet:Tweet:Twitter {id:r})
  MERGE (tweet)-[:REPLIED_TO]->(reply_tweet)
  SET tweet:Reply
)

FOREACH (retweet_id IN [x IN [retweet.id] WHERE x IS NOT NULL] |
    MERGE (retweet_tweet:Tweet:Twitter {id:retweet_id})
    MERGE (tweet)-[:RETWEETED]->(retweet_tweet)
    SET tweet:Retweet
)
"""

def find_last_tweet(neo4j_url, neo4j_user, neo4j_pass):
    with GraphDatabase.driver(neo4j_url, auth=basic_auth(neo4j_user, neo4j_pass)) as driver:
        with driver.session() as session:
            result = session.run("MATCH (t:Tweet:Content) RETURN max(t.id) as sinceId")
            for record in result:
                if record["sinceId"] is not None:
                    return record["sinceId"]

def find_tweets_since(since_id, search, bearer_token):
    q = urllib.parse.quote(search, safe='')
    max_pages = 100

    count = 100
    result_type = "recent"
    lang = "en"

    max_id = -1

    has_more = True
    while has_more:
        api_url = f"https://api.twitter.com/1.1/search/tweets.json?q={q}&count={count}&result_type={result_type}&lang={lang}"
        if since_id != -1:
            api_url += "&since_id=%s" % (since_id)
        if max_id != -1:
            api_url += "&max_id=%s" % (max_id)

        print(f"Processing since [{since_id}] max [{max_id}]")

        response = requests.get(api_url,
            headers = {"accept": "application/json", "Authorization": "Bearer " + bearer_token})
        if response.status_code != 200:
            raise (Exception(response.status_code, response.text))

        json = response.json()

        tweets = json.get("statuses", [])

        meta = json["search_metadata"]

        if meta.get('next_results', None) is not None:
            max_id = meta["next_results"].split("=")[1][0:-2]

        has_more = len(tweets) == count
        print(f"More tweets to fetch? {has_more}")

        if len(tweets) > 0:
            for tweet in tweets:
                yield tweet

        time.sleep(1)

        if json.get('backoff', None) is not None:
            print("backoff", json['backoff'])
            time.sleep(json['backoff'] + 5)





def import_links(neo4j_url, neo4j_user, neo4j_pass, bearer_token, search):
    if len(bearer_token) == 0:
        raise Exception("No Twitter Bearer token configured")

    with GraphDatabase.driver(neo4j_url, auth=basic_auth(neo4j_user, neo4j_pass)) as driver:
        with driver.session() as session:
            q = urllib.parse.quote(search, safe='')
            max_pages = 100
            # False for retrieving history, True for catchup forward
            catch_up = True
            count = 100
            result_type = "recent"
            lang = "en"

            since_id = -1
            max_id = -1
            page = 1

            has_more = True
            while has_more and page <= max_pages:
                if catch_up:
                    result = session.run("MATCH (t:Tweet:Content) RETURN max(t.id) as sinceId")
                    for record in result:
                        print(record)
                        if record["sinceId"] is not None:
                            since_id = record["sinceId"]

                api_url = "https://api.twitter.com/1.1/search/tweets.json?q=%s&count=%s&result_type=%s&lang=%s" % (
                    q, count, result_type, lang)
                if since_id != -1:
                    api_url += "&since_id=%s" % (since_id)
                if max_id != -1:
                    api_url += "&max_id=%s" % (max_id)

                response = requests.get(api_url,
                                        headers={"accept": "application/json",
                                                 "Authorization": "Bearer " + bearer_token})
                if response.status_code != 200:
                    raise (Exception(response.status_code, response.text))

                json = response.json()
                meta = json["search_metadata"]

                if not catch_up and meta.get('next_results', None) is not None:
                    max_id = meta["next_results"].split("=")[1][0:-2]
                tweets = json.get("statuses", [])

                if len(tweets) > 0:
                    result = session.run(import_query, {"tweets": tweets})
                    print(result.consume().counters)
                    page = page + 1

                has_more = len(tweets) == count

                print("catch_up", catch_up, "more", has_more, "page", page, "max_id", max_id,
                      "since_id", since_id, "tweets", len(tweets))
                time.sleep(1)

                if json.get('backoff', None) is not None:
                    print("backoff", json['backoff'])
                    time.sleep(json['backoff'] + 5)

unhydrated_query = """\
MATCH (link:Link)
WHERE not exists(link.title)
RETURN id(link) as id, link.url as url
ORDER BY ID(link) DESC
LIMIT {limit}
"""


def hydrate_links(neo4j_url, neo4j_user, neo4j_pass):
    with GraphDatabase.driver(neo4j_url, auth=basic_auth(neo4j_user, neo4j_pass)) as driver:
        with driver.session() as session:
            result = session.run(unhydrated_query, {"limit": 100})

            rows = 0
            for record in result:
                try:
                    print("Processing {0}".format(record["url"]))
                    title = hydrate_url(record["url"])
                    rows += 1
                    update_graph(session, {"id": record["id"], "title": title})
                except AttributeError:
                    print("Failed to resolve {0}. Ignoring for now".format(record["url"]))
                    update_graph(session, {"id": record["id"], "title": "N/A"})
                except socket.gaierror:
                    print("Failed to resolve {0}. Ignoring for now".format(record["url"]))
                    update_graph(session, {"id": record["id"], "title": "N/A"})
                except socket.error:
                    print("Failed to connect to {0}. Ignoring for now".format(record["url"]))
                    update_graph(session, {"id": record["id"], "title": "N/A"})

            print("records", rows)


def update_graph(session, update):
    result = session.run(
        "WITH {data} AS row MATCH (link) WHERE id(link) = row.id SET link.title = row.title",
        {"data": update})
    print(result.consume().counters)


def hydrate_url(url):
    user_agent = {'User-agent': 'Mozilla/5.0'}
    potential_title = []
    try:
        if url:
            r = requests.get(url, headers=user_agent, timeout=5.0)
            response = r.text
            page = BeautifulSoup(response, "html.parser")
            potential_title = page.find_all("title")
    except requests.exceptions.ConnectionError:
        print("Failed to connect: ", url)
    except requests.exceptions.ReadTimeout:
        print("Read timed out: ", url)

    if len(potential_title) == 0:
        print("Skipping: ", url)
        return "N/A"
    else:
        return potential_title[0].text


def unshorten_url(url):
    session = requests.Session()  # so connections are recycled
    resp = session.head(url, allow_redirects=True)
    return resp.url

not_cleaned_links_query = """\
MATCH (l:Link)
WHERE not(exists(l.short)) AND not(exists(l.cleanUrl))
RETURN l, ID(l) AS internalId
ORDER BY internalId DESC
"""

update_links_query = """\
UNWIND {updates} AS update
MATCH (l:Link) WHERE ID(l) = update.id
SET l.cleanUrl = update.clean
"""


def clean_links(neo4j_url, neo4j_user, neo4j_pass):
    with GraphDatabase.driver(neo4j_url, auth=basic_auth(neo4j_user, neo4j_pass)) as driver:
        with driver.session() as session:
            result = session.run(not_cleaned_links_query)

            updates = []
            for row in result:
                uri = row["l"]["url"]
                if uri:
                    print("(Before) URL to clean:", uri)
                    uri = uri.encode('utf-8')
                    print("(After) URL to clean:", uri)
                    try:
                        updates.append({"id": row["internalId"], "clean": clean_uri(uri)})
                    except UnicodeDecodeError:
                        print("Unable to clean {0}".format(uri))

            print("Updates to apply", updates)

            update_result = session.run(update_links_query, {"updates": updates})

            print(update_result)


def clean_uri(url):
    u = urlparse(url)
    query = parse_qs(u.query.decode("utf-8"))

    for param in ["utm_content", "utm_source", "utm_medium", "utm_campaign", "utm_term"]:
        query.pop(param, None)

    u = u._replace(query=bytes(urlencode(query, True), "utf-8"))

    return urlunparse(u).decode("utf-8")