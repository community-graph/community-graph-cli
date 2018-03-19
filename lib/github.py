import datetime
import json
import time
from datetime import timezone

import requests
from dateutil.parser import parse
from neo4j.v1 import GraphDatabase, basic_auth

import_query = """
WITH {json} as data
UNWIND data.items as r
MERGE (repo:Repository:GitHub {id:r.id})
ON CREATE SET
    repo.title = r.name, repo.full_name=r.full_name, repo.url = r.html_url,
    repo.created = apoc.date.parse(r.created_at,'ms',"yyyy-MM-dd'T'HH:mm:ss'Z'"), repo.created_at = r.created_at,
    repo.homepage = r.homepage
SET repo.favorites = r.stargazers_count,
    repo.updated = apoc.date.parse(r.updated_at,'ms',"yyyy-MM-dd'T'HH:mm:ss'Z'"),
    repo.updated_at = r.updated_at,
    repo.pushed = apoc.date.parse(r.pushed_at,'ms',"yyyy-MM-dd'T'HH:mm:ss'Z'"),
    repo.pushed_at = r.pushed_at,
    repo.size = r.size,
    repo.watchers = r.watchers, repo.language = r.language, repo.forks = r.forks_count,
    repo.open_issues = r.open_issues, repo.branch = r.default_branch, repo.description = r.description,
    repo.isPrivate = r.isPrivate

MERGE (owner:GitHubAccount {id:r.owner.id})
SET owner:User, owner:GitHub, owner.name = r.owner.login, owner.type=r.owner.type, owner.full_name = r.owner.name,
    owner.location = r.owner.location, owner.avatarUrl = r.owner.avatarUrl
MERGE (owner)-[:CREATED]->(repo)
WITH repo, r
UNWIND r.releases AS release
MERGE (releaseAsset:ReleaseAsset {name: repo.title + "-" + release.name })
SET releaseAsset.jar = release.name
WITH repo, releaseAsset, release
CALL apoc.create.setProperty( releaseAsset, apoc.date.format(timestamp(), "ms",  "yyyy-MM-dd"), release.downloadCount) 
YIELD node 
MERGE (repo)-[:RELEASE_ASSET]->(node)
"""

graphql_query = """\
query Repositories($searchTerm: String!, $cursor: String) {
  rateLimit {
    limit
    cost
    remaining
    resetAt
  }
  search(query: $searchTerm, type: REPOSITORY, first: 100, after: $cursor) {
    repositoryCount
    pageInfo {
      hasNextPage
      endCursor
    }
    nodes {
      __typename
      ... on Repository {
        releases(first: 50) {
          nodes {
            releaseAssets(first: 1) {
              nodes {
                name
                downloadCount
              }
            }
          }
        }
        databaseId
        isPrivate
        name
        url
        pushedAt
        createdAt
        updatedAt
        diskUsage
        description
        homepageUrl
        issues {
          totalCount
        }
        stargazers {
          totalCount
        }
        watchers {
          totalCount
        }
        forks {
          totalCount
        }
        languages(first: 1, orderBy: {field: SIZE, direction: DESC}) {
          nodes {
            name
          }
        }
        owner {
          __typename
          login
          avatarUrl
          ... on User {
            name
            databaseId
            location
          }
          ... on Organization {
            name
            databaseId
          }
        }
        defaultBranchRef {
          name
        }
      }
    }
  }
}

"""


class GitHubImporter:
    def __init__(self, neo4j_url, neo4j_user, neo4j_pass, github_token):
        self.neo4j_url = neo4j_url
        self.neo4j_user = neo4j_user
        self.neo4j_pass = neo4j_pass
        self.github_token = github_token

    def process_tag(self, tags, start_date, end_date):
        with GraphDatabase.driver(self.neo4j_url, auth=basic_auth(self.neo4j_user, self.neo4j_pass)) as driver:
            with driver.session() as session:
                tag = " OR ".join(tags)
                print("Processing projects from {0} to {1}. Tag: [{2}]".format(start_date, end_date, tag))
                search = "{0} size:>0 pushed:{1}..{2}".format(tag, start_date, end_date)
                cursor = None
                print("Search term: {0}".format(search))
                has_more = True
                while has_more:
                    apiUrl = "https://api.github.com/graphql"

                    data = {
                        "query": graphql_query,
                        "variables": {"searchTerm": search, "cursor": cursor}
                    }

                    bearer_token = "bearer {token}".format(token=self.github_token)
                    response = requests.post(apiUrl,
                                             data=json.dumps(data),
                                             headers={"accept": "application/json",
                                                      "Authorization": bearer_token})

                    if response.status_code != 200:
                        print("Request failed with status code {code}".format(code=response.status_code))
                        print(response.text)
                        return

                    r = response.json()
                    if not r["data"]:
                        print("Response doesn't contain a 'data' section so we can't continue")
                        print("Params: {0}".format(tags))
                        print(response.text)
                        return

                    the_json = []
                    search_section = r["data"]["search"]
                    for node in search_section["nodes"]:
                        languages = [n["name"] for n in node["languages"]["nodes"]]
                        default_branch_ref = node.get("defaultBranchRef") if node.get("defaultBranchRef") else {}
                        full_name = "{login}/{name}".format(name=node["name"], login=node["owner"]["login"])

                        releases = []
                        for release in node["releases"]["nodes"]:
                            release_assets = release["releaseAssets"]["nodes"]
                            if len(release_assets) > 0:
                                releases.append({
                                    "name": release_assets[0]["name"],
                                    "downloadCount": release_assets[0]["downloadCount"]
                                })

                        if not node["isPrivate"]:
                            params = {
                                "id": node["databaseId"],
                                "isPrivate": node["isPrivate"],
                                "name": node["name"],
                                "full_name": full_name,
                                "created_at": node["createdAt"],
                                "pushed_at": node["pushedAt"],
                                "updated_at": node["updatedAt"],
                                "size": node["diskUsage"],
                                "homepage": node["homepageUrl"],
                                "stargazers_count": node["forks"]["totalCount"],
                                "forks_count": node["stargazers"]["totalCount"],
                                "watchers": node["watchers"]["totalCount"],
                                "owner": {
                                    "id": node["owner"].get("databaseId", ""),
                                    "login": node["owner"]["login"],
                                    "avatarUrl": node["owner"]["avatarUrl"],
                                    "name": node["owner"].get("name", ""),
                                    "type": node["owner"]["__typename"],
                                    "location": node["owner"].get("location", "")
                                },
                                "default_branch": default_branch_ref.get("name", ""),
                                "open_issues": node["issues"]["totalCount"],
                                "description": node["description"],
                                "html_url": node["url"],
                                "language": languages[0] if len(languages) > 0 else "",
                                "releases": releases
                            }

                            the_json.append(params)
                        else:
                            print("Skipping private repository", full_name)

                    has_more = search_section["pageInfo"]["hasNextPage"]
                    cursor = search_section["pageInfo"]["endCursor"]

                    result = session.run(import_query, {"json": {"items": the_json}})
                    print(result.consume().counters)

                    reset_at = r["data"]["rateLimit"]["resetAt"]
                    time_until_reset = (parse(reset_at) - datetime.datetime.now(timezone.utc)).total_seconds()

                    if r["data"]["rateLimit"]["remaining"] <= 0:
                        time.sleep(time_until_reset)

                    print("Reset at:", time_until_reset,
                        "has_more", has_more,
                        "cursor", cursor,
                        "repositoryCount", search_section["repositoryCount"])

def import_github(neo4j_url, neo4j_user, neo4j_pass, tag, github_token):
    importer = GitHubImporter(neo4j_url, neo4j_user, neo4j_pass, github_token)
    for tags in chunker(tag, 5):
        start_date = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        end_date = datetime.datetime.now().strftime("%Y-%m-%d")
        importer.process_tag(tags, start_date, start_date)


def chunker(seq, size):
    return (seq[pos:pos + size] for pos in range(0, len(seq), size))