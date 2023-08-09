# Copyright 2023 Province of British Columbia
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at 
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

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
    
