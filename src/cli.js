const prompt = require('prompt');

schema = {
    properties: {
        communityName: {
            description: 'Name of your community',
            required: true
        },
        serverUrl: {
            description: "URL of your Neo4j server (leave blank if you don't have one, and one will be created)",
        },
        serverUsername: {
            description: 'Neo4j server username',
            ask: function () {
                return prompt.history('serverUrl').value != "";
            }
        },
        serverPassword: {
            description: 'Neo4j server password',
            ask: function () {
                return prompt.history('serverUrl').value != "";
            }
        },
        readOnlyServerUsername: {
            description: 'Neo4j read only server username',
            ask: function () {
                return prompt.history('serverUrl').value != "";
            }
        },
        readOnlyServerPassword: {
            description: 'Neo4j read only server password',
            ask: function () {
                return prompt.history('serverUrl').value != "";
            }
        },
        tag: {
            description: 'Search term for use on GitHub/SO/Meetup (Ctrl + C when all tags added)',
            required: true,
            type: 'array',
            minItems: 1
        },
        twitterSearch: {
            description: 'Search term for finding links on Twitter',
            required: true
        },
        twitterBearer: {
            description: 'Twitter Bearer',
            required: true
        },
        githubToken: {
            description: 'GitHub Token',
            required: true
        },
        meetupApiKey: {
            description: 'Meetup API key',
            required: true
        },
        stackOverflowApiKey: {
            description: 'StackOverflow API key',
            required: true
        },
        s3Bucket: {
            description: "Name of S3 bucket where the dashboard should be generated (leave blank if you don't have one, and one will be created)",
        },
        logo: {
            description: 'Link to a logo to use for your community graph',
        },
        kmsKeyArn: {
            description: "KMS Key Arn (leave blank if you don't have one, and one will be created)",
        },
    }
}

function getParameters(data) {
    prompt.start();
    
    return new Promise((resolve, reject) => {                                
        prompt.get(schema, function (err, result) {            
            resolve(result)
        });
    });
}

module.exports = {
    getParameters: getParameters,
    schema: schema
}