import os
import boto3
import json


generate_ip = "powershell \"aws ec2 describe-instances --profile srv_user_incb --filters Name=tag:srv_name,Values=srv-incubus \
                --query 'Reservations[*].Instances[*].PublicIpAddress' --output text > server_ip.txt\" && exit"
#print(generate_ip)
#os.system(generate_ip)

#with open ("server_ip.txt","r",  encoding='utf-8', errors="ignore") as arquivo:
 #   teste = arquivo.read()


session = boto3.Session(profile_name="srv_user_incb")
client_ec2 = session.client('ec2')
client_s3 = session.client('s3')
resource_s3 = boto3.resource('s3')

response = client_ec2.describe_instances(
    Filters=[
            {
                'Name': 'tag:srv_name',
                'Values': [
                    'srv-incubus',
                ]
            },
        ]
)

response_s3 = client_s3.list_buckets()

print(response_s3)
print(response['Reservations'][0]["Instances"][0]['PublicIpAddress'])








