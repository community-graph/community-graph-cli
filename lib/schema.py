from neo4j.v1 import GraphDatabase, basic_auth

def configure_constraints(neo4j_url, neo4j_user, neo4j_pass):
    with GraphDatabase.driver(neo4j_url, auth=basic_auth(neo4j_user, neo4j_pass)) as driver:
        with driver.session() as session:            
            session.run("CREATE CONSTRAINT ON (t:Tweet) ASSERT t.id IS UNIQUE")
            session.run("CREATE CONSTRAINT ON (u:User) ASSERT u.screen_name IS UNIQUE")            
            session.run("CREATE CONSTRAINT ON (g:GitHubAccount) ASSERT g.id IS UNIQUE")
            session.run("CREATE CONSTRAINT ON (s:StackOverflowAccount) ASSERT s.id IS UNIQUE")
            session.run("CREATE INDEX ON :Tag(name)")
            session.run("CREATE INDEX ON :Link(url)")
            session.run("CREATE INDEX ON :Tweet(created)")