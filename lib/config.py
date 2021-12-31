import os
def read_config():
    # config_file = os.getenv('CONFIG_FILE', 'communitygraph.json')
    # print("Reading config from {config_file}".format(config_file=config_file))
    # with open(config_file) as data_file:
    #     return json.load(data_file)
    return {
        "communityName": os.environ['COMMUNITY_NAME'],
        "s3Bucket": os.environ['S3_BUCKET'],
        "tag": os.environ['TAGS'].split(','),
        "logo": os.environ['NEO4J_LOGO'],
        "serverUrl": os.environ['NEO4J_HOST'],
        "twitterSearch": os.environ['TWITTER_SEARCH'],
        "credentials": {
            "githubToken": os.environ['GITHUB_TOKEN'],
            "twitterBearer" : os.environ['TWITTER_BEARER'],
            "meetupApiKey": os.environ['MEETUP_API_KEY'],
            "readonly": {
                "user": os.environ['NEO4J_USER'],
                "password": os.environ['NEO4J_PASS']
            },
            "write": {
                "user": os.environ['NEO4J_USER'],
                "password": os.environ['NEO4J_PASS']
            }

        },
    }
