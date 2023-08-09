# TODO: insert copyright code 

#######################################################
#                                                     #
# Functions to aid in fetching data from warehouse    #
#                                                     #
#######################################################

# IMPORTS 
# system stuff
import re
import os

# connection stuff
import pyodbc
from sqlalchemy import create_engine
from urllib import parse

# standard stuff
import pandas as pd


# get connection to database
def create_connection(cred_path, sqlalchemy=False):  
    connection_str = ''
    with open(cred_path) as infile:
        for line in infile:
            connection_str += line.strip('\n')

    if sqlalchemy:
        # Create a URL for SQLAlchemy's engine
        params = parse.quote_plus(connection_str)
        connection = create_engine("mssql+pyodbc:///?odbc_connect=%s" % params, use_setinputsizes=False)
    
    else:
        connection = pyodbc.connect(connection_str)

    return connection


# read in data to dataframes
def fetch_table(table_name, connection):
    df = pd.read_sql(f'SELECT * FROM {table_name}', connection)
    df.columns = [x.lower().replace(' ','_') for x in df.columns]

    return df


# send dataframe back to warehouse
def save_table(df, table_name, connection, how='replace'):
 
    if how.lower() not in ['replace', 'append']:
        print("Method of saving data not in options ['replace', 'append'].")
        print("Table not saved.")
        return

    df.to_sql(
        table_name, 
        con=connection, 
        if_exists=how, 
        index=False
        )
    
