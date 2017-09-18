import time
import requests

from neo4j.v1 import GraphDatabase, basic_auth

import_meetup_events_query = """
UNWIND {json} as e
MATCH (g:Group {id:e.group.id})
WITH e,g WHERE (g:Graph OR (e.name + e.description) =~ "(?is).*(graph|neo4j).*")
MERGE (event:Event:Meetup {id:e.id}) 
ON CREATE SET event.title=e.name,event.text=e.description,event.created=e.created,
event.link=e.event_url,event.time=e.time,
event.utc_offset=e.utc_offset,event.duration=e.duration
SET event.updated=e.updated,event.headcount=e.headcount,event.waitlist_count=e.waitlist_count,
event.maybe_rsvp_count=e.maybe_rsvp_count,event.yes_rsvp_count=e.yes_rsvp_count,event.rsvp_limit=e.rsvp_limit,
event.announced=e.announced,event.comment_count=e.comment_count,event.status=e.status,event.rating=e.rating.average,event.ratings=e.rating.count
MERGE (g)-[:CONTAINED]->(event)
FOREACH (o in coalesce(e.event_hosts,[]) |
  MERGE (host:User:Meetup {id:o.member_id}) ON CREATE SET host.name = o.member_name
  MERGE (host)-[:CREATED]->(event)
)

WITH event, e.venue as v
WHERE v IS NOT NULL AND v.id IS NOT NULL
MERGE (venue:Venue:Meetup {id:v.id}) ON CREATE SET venue.name=v.name, venue.longitude=v.lon,venue.latitude=v.lat,venue.country = v.country, venue.city=v.city,venue.address=v.address_1,venue.country_name = v.localized_country_name

MERGE (venue)-[:HOSTED]->(event)
"""

import_meetup_groups_query = """
UNWIND {json} as g
MERGE (group:Group:Meetup:Container {id:g.id}) 
  ON CREATE SET group.title=g.name,group.text=g.description,group.key=g.urlname,group.country=g.country,group.city=g.city,group.created=g.created,group.link=g.link,group.longitude=g.lon,group.latitude=g.lat,group.members=g.members
SET group.rating=g.rating
FOREACH (organizer IN [o in [g.organizer] WHERE g.organizer IS NOT NULL] |
  MERGE (owner:User:Meetup {id:organizer.member_id}) ON CREATE SET owner.name = organizer.name
  MERGE (owner)-[:CREATED]->(group)
)

FOREACH (t IN g.topics | MERGE (tag:Tag:Meetup {name:t.urlkey}) ON CREATE SET tag.id = t.id, tag.description=t.name MERGE (group)-[:TAGGED]->(tag))
WITH group WHERE (group.title + group.text) =~ "(?is).*(graph|neo4j).*"
SET group:Graph
"""


def import_events(neo4j_url, neo4j_user, neo4j_pass, meetup_key):
    if len(meetup_key) == 0:
        raise (Exception("No Meetup API Key configured"))

    with GraphDatabase.driver(neo4j_url, auth=basic_auth(neo4j_user, neo4j_pass)) as driver:
        with driver.session() as session:
            groups = []
            result = session.run("MATCH (g:Group:Meetup) RETURN g.id as id, g.key as key")
            for record in result:
                if record["id"] != None:
                    group = record["id"]
                    groups += [str(group)]
            event_url = "https://api.meetup.com/2/events?group_id={groups}&status=upcoming,past&text_format=plain&order=time&omit=fee,photo_sample,rsvp_rules,rsvp_sample&fields=event_hosts".format(
                groups=",".join(groups))
            run_import("events", event_url, session, import_meetup_events_query, meetup_key, {})


def import_groups(neo4j_url, neo4j_user, neo4j_pass, tag, meetup_key):
    if len(meetup_key) == 0:
        raise (Exception("No Meetup API Key configured"))
    if len(tag) == 0:
        raise Exception("No tag configured")

    with GraphDatabase.driver(neo4j_url, auth=basic_auth(neo4j_user, neo4j_pass)) as driver:
        with driver.session() as session:
            group_url = "https://api.meetup.com/2/groups?topic={tag}&radius=36000&text_format=plain&order=id&omit=contributions,group_photo,approved,join_info,membership_dues,self,similar_groups,sponsors,simple_html_description,welcome_message".format(tag=tag)
            run_import("groups", group_url, session, import_meetup_groups_query, meetup_key, {})


def run_import(type, url, session, query, meetup_key, params):
    page = 0
    has_more = True
    items = 100

    while has_more:
        api_url = url + "&key={key}&offset={offset}&page={items}".format(key=meetup_key, offset=page, items=items)

        response = requests.get(api_url, headers={"accept": "application/json"})
        if response.status_code != 200:
            print(response.text)

        rate_remain = int(response.headers['X-RateLimit-Remaining'])
        rate_reset = int(response.headers['X-RateLimit-Reset'])

        json = response.json()
        meta = json['meta']
        results = json.get("results", [])
        has_more = len(meta.get("next", "")) > 0
        if len(results) > 0:
            p = {"json": results}
            p.update(params)
            result = session.run(query, p)
            print(result.consume().counters)
            page = page + 1

        print(type, "results", len(results), "has_more", has_more, "quota", rate_remain, "reset (s)", rate_reset, "page", page)
        time.sleep(1)
        if rate_remain <= 0:
            time.sleep(rate_reset)
