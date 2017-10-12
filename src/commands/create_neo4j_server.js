const program = require('commander');
const fs = require('fs');
const aws = require("../aws");
const AWS = require("aws-sdk");
const uuidv4 = require('uuid/v4');

let regionParams = { 'region': 'us-east-1' }
var ec2 = new AWS.EC2(regionParams);

program
    .arguments("<communityName>")
    .option('-d, --dry-run', 'Is this a dry run?')
    .parse(process.argv);

var values = program.args;
if (!values.length) {
    console.error('You must provide a name for your community');
    program.help();
    process.exit(1);
}

let communityName = values[0];

console.log(`Creating a Neo4j server for community ${communityName}`);

let dryRun = program.dryRun || false;

let serverParams = {};
let uuid = uuidv4();
serverParams.keyName = `community-graph-keypair-${communityName}-${uuid}`;
serverParams.groupName = `community-graph-security-${communityName}-${uuid}`;

ec2.createKeyPair({ KeyName: serverParams.keyName, DryRun: dryRun }).promise().then(data => {
    console.log("Key pair created. Save this to a file - you'll need to use it if you want to SSH into the Neo4j server");
    console.log(data['KeyMaterial']);
    return ec2.createSecurityGroup({ Description: "Community Graph Security Group", GroupName: serverParams.groupName, DryRun: dryRun }).promise()
}).then(data => {
    console.log("Created Group Id:" + data.GroupId);
    serverParams["groupId"] = data.GroupId;
    var ports = [22, 7474, 7473, 7687];
    return Promise.all(ports.map(function (port) {
        let params = {
            GroupId: data.GroupId,
            IpProtocol: "tcp",
            FromPort: port,
            ToPort: port,
            CidrIp: "0.0.0.0/0",
            DryRun: dryRun
        };
        return ec2.authorizeSecurityGroupIngress(params).promise();
    }));
}).then(data => {
    console.log("Opened Neo4j ports");
    let params = {
        ImageId: "ami-f03c4fe6",
        MinCount: 1,
        MaxCount: 1,
        InstanceType: "m3.medium",
        KeyName: serverParams.keyName,
        SecurityGroupIds: [serverParams.groupId],
        DryRun: dryRun,
        UserData: new Buffer(`#!/bin/bash \n
        curl -L https://github.com/neo4j-contrib/neo4j-apoc-procedures/releases/download/3.2.0.3/apoc-3.2.0.3-all.jar -O \n
        sudo cp apoc-3.2.0.3-all.jar /var/lib/neo4j/plugins/ \n`).toString('base64')
    };
    return ec2.runInstances(params).promise();
}).then(data => {
    let ourInstance = data.Instances[0];
    console.log("Instance Id: " + ourInstance.InstanceId);
    serverParams.instanceId = ourInstance.InstanceId;

    let params = {
        InstanceIds: [ourInstance.InstanceId]
    };
    return ec2.waitFor("instanceRunning", params).promise();
}).then(data => {
    let reservations = data.Reservations;
    let instances = reservations[0].Instances;
    serverParams.publicDnsName = instances[0].PublicDnsName;

    console.log("Your Neo4j server is now ready!");
    console.log("You'll need to login to the server and change the default password:")
    console.log(`http://${serverParams.publicDnsName}:7474`)
    console.log(`User:neo4j, Password:${serverParams.instanceId}`)
    console.log("You can also create a Read Only user, which will be used for non write operations, by running the following procedure:")
    console.log(`call dbms.security.createUser("<username>", "<password>", false)`);

}).catch(err => console.log(err, err.stack));