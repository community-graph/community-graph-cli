import lib.summary as summary
import json

def generate_page_summary(event, _):
    print("Event:", event)

    with open('.communitygraph') as data_file:
        config = json.load(data_file)

    url = config["serverUrl"]

    read_only_credentials = config["credentials"]["readonly"]
    user = read_only_credentials["user"]
    password = read_only_credentials["password"]

    title = config["communityName"]
    short_name = config["s3Bucket"]
    logo_src = config["logo"]

    summary.generate(url, user, password, title, short_name, logo_src)
