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

MERGE (owner:User:GitHub {id:r.owner.id})
SET owner.name = r.owner.login, owner.type=r.owner.type, owner.full_name = r.owner.name,
    owner.location = r.owner.location, owner.avatarUrl = r.owner.avatarUrl
MERGE (owner)-[:CREATED]->(repo)
"""

graphql_query = """\
query Repositories($searchTerm: String!, $cursor: String) {
 rateLimit {
    limit
    cost
    remaining
    resetAt
 }
 search(query:$searchTerm, type: REPOSITORY, first: 100, after: $cursor) {
   repositoryCount
   pageInfo {
        hasNextPage
        endCursor
   }
   nodes {
     __typename
     ... on Repository {
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
       issues { totalCount }
       stargazers { totalCount }
       watchers { totalCount }
       forks { totalCount }

       languages(first:1, orderBy: {field: SIZE, direction:DESC}) {
         nodes { name }
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
        defaultBranchRef { name }
     }
   }
 }
}
"""


def import_github(neo4j_url, neo4j_user, neo4j_pass, tag, github_token):
    with GraphDatabase.driver(neo4j_url, auth=basic_auth(neo4j_user, neo4j_pass)) as driver:
        with driver.session() as session:
            from_date = (datetime.datetime.now() - datetime.timedelta(days=90)).strftime("%Y-%m-%d")

            print("Processing projects from {0}".format(from_date))

            search = "{0} pushed:>{1}".format(tag, from_date)
            cursor = None
            has_more = True

            while has_more:
                apiUrl = "https://api.github.com/graphql"

                data = {
                    "query": graphql_query,
                    "variables": {"searchTerm": search, "cursor": cursor}
                }

                bearer_token = "bearer {token}".format(token=github_token)
                response = requests.post(apiUrl,
                                         data=json.dumps(data),
                                         headers={"accept": "application/json",
                                                  "Authorization": bearer_token})
                r = response.json()

                the_json = []
                search_section = r["data"]["search"]
                for node in search_section["nodes"]:
                    languages = [n["name"] for n in node["languages"]["nodes"]]
                    default_branch_ref = node.get("defaultBranchRef") if node.get("defaultBranchRef") else {}
                    full_name = "{login}/{name}".format(name=node["name"], login=node["owner"]["login"])

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
                            "language": languages[0] if len(languages) > 0 else ""
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
