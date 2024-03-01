
import psycopg2
from psycopg2.extras import RealDictCursor
from sshtunnel import SSHTunnelForwarder
from pandas import DataFrame as pd
import json
import boto3
from io import StringIO
import os


# Inicia um sessão na AWS
session = boto3.Session(profile_name=your_profile_created_in_aws_cli)
bucket = your_bucket_name

# Extrai endereço IP do Host do Postgres no EC2 filtrando pela tag que vc criou

client_ec2 = session.client('ec2')
#resource_s3 = session.resource('s3')
client_s3 = session.client('s3')

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

host_atual_address =response['Reservations'][0]["Instances"][0]['PublicIpAddress']

# Lista de Extração dos ETLs

extract_list = [ ['Postgres ED', r"ETL_POSTGRES_EC2_TO_S3/queries/_sql/clientes.sql", "bronze/stg_clientes.csv"],
                ['Postgres ED', r"ETL_POSTGRES_EC2_TO_S3/queries/_sql/itenvenda.sql", "bronze/stg_iten_venda.csv"],
                ['Postgres ED', r"ETL_POSTGRES_EC2_TO_S3/queries/_sql/produtos.sql", "bronze/stg_produtos.csv"],
                ['Postgres ED', r"ETL_POSTGRES_EC2_TO_S3/queries/_sql/vendas.sql", "bronze/stg_vendas.csv"],
                ['Postgres ED', r"ETL_POSTGRES_EC2_TO_S3/queries/_sql/vendedores.sql", "bronze/stg_vendedores.csv"]
                ]



def extract_data (jump_hostname, jump_username, ssh_ppkey_file, postgres_port, postgres_database, postgres_user, postgres_pwd, extract_query_str):
#   tunnel ssh para o servidor
    tunnel =  SSHTunnelForwarder(
            (jump_hostname, 22),
            ssh_username=jump_username,
            ssh_pkey=ssh_ppkey_file,
            remote_bind_address=('localhost', postgres_port))
    tunnel.start()

#   extrai query
    
    conn = psycopg2.connect(dbname=postgres_database, user=postgres_user, password=postgres_pwd, host='127.0.0.1', port=tunnel.local_bind_port)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(extract_query_str)
    result = cur.fetchall()
    df = pd(result)
    cur.close()
    conn.close()
    return df


# transformador de dados

def transform_data(df):
    colunas = list(df.columns)
    for coluna in colunas:
        if coluna.startswith("dt" or coluna.startswith("data")):
            pass
        elif df[coluna].dtype == "float64" or df[coluna].dtype == "int64":
            df[coluna] = df[coluna].fillna(0)
            df[coluna] = df[coluna].astype(str)
            df[coluna] = df[coluna].str.normalize('NFKD').str.encode("ascii", errors="ignore")\
                        .str.decode('utf-8').str.upper().str.replace('[\n;,"|]', '', regex=True)\
                        .str.replace("'", "", regex=True)
        elif df[coluna].dtype == "bool":
            df[coluna] = df[coluna].astype(bool).astype(int)
        else:
            df[coluna] = df[coluna].astype(str)
            df[coluna] = df[coluna].str.replace(r"^None^", "", regex=True)
            df[coluna] = df[coluna].str.normalize('NFKD').str.encode("ascii", errors="ignore")\
                        .str.decode('utf-8').str.upper().str.replace('[\n;,"|]', '', regex=True)\
                        .str.replace("'", "", regex=True)
    return(df)

        
def load_data_to_s3(df,  bucket, s3_path):
    #s3 = boto3.client("s3", aws_access_key_id = s3_acc_key, aws_secret_access_key = s3_sct_key)
    csv_buf = StringIO()
    df.to_csv(csv_buf, header=True, index=False, sep="|", escapechar="|")
    csv_buf.seek(0)
    client_s3.put_object(Bucket=bucket, Body=csv_buf.getvalue(), Key=s3_path)


# extrator de dados
def main():

#   abre arquivo de conexão
    with open(r"C:\config_files\database_conn.txt") as conn_file_opened:
        conn_file_read = json.loads(conn_file_opened.read())

#   popula variaveis
    for extract_parameters in extract_list:
            jump_hostname = host_atual_address
            jump_username = conn_file_read[extract_parameters[0]]["host_username"]
            ssh_ppkey_file = conn_file_read[extract_parameters[0]]["ssh_pkey_file"]
            postgres_host = conn_file_read[extract_parameters[0]]["db_host"]
            postgres_database = conn_file_read[extract_parameters[0]]["db_name"]
            postgres_user = conn_file_read[extract_parameters[0]]["db_username"]
            postgres_pwd =  conn_file_read[extract_parameters[0]]["db_pwd"]
            postgres_port = conn_file_read[extract_parameters[0]]["db_port"]
            extract_query_str = open(extract_parameters[1], 'rb').read().decode("UTF-8")
            s3_path = extract_parameters[2]

            list_index = extract_list.index(extract_parameters)+1
            list_len = len(extract_list)
            print(f"...Iniciando extração {list_index}de {list_len}...\n")
            print(f"Extraindo dados de {extract_parameters[1]}...")
            df = extract_data (jump_hostname, jump_username, ssh_ppkey_file, postgres_port, postgres_database, postgres_user, postgres_pwd, extract_query_str)
            print(f"Dados de {extract_parameters[1]} extraídos com sucesso!")
            print(f"...Iniciando transformação e dados de {extract_parameters[1]}...")
            df = transform_data(df)
            print(f"Transformação de {extract_parameters[1]} concluída com sucesso!")
            print(f"...Gravando dados no S3 em {extract_parameters[2]}...\n")
            load_data_to_s3(df, bucket, s3_path)
            print(f"Finalizando gravação {list_index}de {list_len}... \n")
            
            if extract_list.index(extract_parameters) == len(extract_list)-1:
                print(f"Processo concluído com sucesso, total de {list_len} arquivo(s) processados!")

if __name__ == "__main__":
    main()    