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
# Functions to aid in cleaning data                   #
#                                                     #
#######################################################

# IMPORTS 
# system stuff
import re
import os

# standard stuff
import pandas as pd
import numpy as np

# country info
from countryinfo import CountryInfo

# nlp stuff
from fuzzywuzzy import fuzz
from autocorrect import Speller


# split a list of descriptor words into a list 
def split_description(description):

    # check for NULLs
    if description is None:
        return []
        
    # split string based on comma delimiters, as well as words in brackets
    desc_list = re.split(r'\sand\s|\sor\s|including|[,;()\r\n]+', description)

    # lower case, remove extra characters and remove spaces
    desc_list = [x.lower().replace('"', '').replace('_', '').strip(' ') for x in desc_list]

    # remove descriptors that are empty
    desc_list = [x for x in desc_list if x!='']

    return desc_list


# create a long form codes dataframe. one line per descriptor word
def get_long_form_codes(code_df):
    code_dict_long = { 'code': [], 'code_desc': [], 'description': [] }

    for idx, row in code_df.iterrows():
        code = str(row.q_code)
        code_desc = row.qc_desc

        qc_desc = split_description(row.qc_desc)
        qc_desc_notes = split_description(row.qc_desc_notes)
        additional_notes = split_description(row.additional_notes)

        all_desc = qc_desc + qc_desc_notes + additional_notes

        # remove duplicates 
        all_desc = [*set(all_desc)]
        
        n_desc = len(all_desc)

        if n_desc==0:
            continue

        # append to dictionary
        code_dict_long['code'].extend([code]*n_desc)
        code_dict_long['code_desc'].extend([code_desc]*n_desc)
        code_dict_long['description'].extend(all_desc)

    code_df_long = pd.DataFrame(code_dict_long)

    return code_df_long


# Use autocorrect pacakage to correct typos
def correct_spelling(sentence):
    spell = Speller()
    corrected_sentence = spell(sentence)
    return corrected_sentence


# get the fuzzy scores for each response compared against
# each descriptor word in code base
def get_scores(response, code_df_long, as_df = False):
    
    # response = correct_spelling(response).lower()
    response = response.lower()

    tmp = code_df_long.copy()
    tmp['ratio'] = code_df_long.description.apply(lambda x: fuzz.ratio(x, response))
    tmp['partial'] = code_df_long.description.apply(lambda x: fuzz.partial_ratio(x, response))
    tmp['sort'] = code_df_long.description.apply(lambda x: fuzz.token_sort_ratio(x, response))
    tmp['set'] = code_df_long.description.apply(lambda x: fuzz.token_set_ratio(x, response))
    tmp['id'] = code_df_long.code + '_' + code_df_long.description
    
    tmp = pd.melt(tmp, id_vars = ['id'], value_vars=['ratio', 'partial', 'sort', 'set'])
    
    tmp['col_id'] = tmp.id + '_' + tmp.variable

    tmp = tmp[['col_id', 'value']]
    
    # use as_df to return the list of names for headers
    if as_df:
        return tmp
    else:
        return tmp.value
    

# if given a dataframe, determine the scores for each response in the frame
def get_scores_from_df(response_df, response_column, code_df_long, headers=None):
    if headers is None:
        headers = list(get_scores('test', code_df_long, as_df = True).col_id.values)
    else:
        # only want the non 'response' columns from an input list of headers
        if headers[0] == 'response':
            headers = headers[1:]

    df = response_df[response_column].apply(lambda x: get_scores(x, code_df_long, as_df=False))
    df.columns = headers
    df['response'] = response_df[response_column]
    df = df[['response'] + headers]
    
    return df


# for hardcoded training data, convert to wide form
# 1/0 binary responses for each category
def get_outputs_wide(df, response_column, code_df_long, output_columns, n_columns):
    code_list = code_df_long.code.unique()

    output_df = pd.DataFrame(columns = ['response'] + list(code_list))

    for idx, row in df.iterrows():
        response = row[response_column]
        code_vals = [0]*len(code_list)
        # cycle through all the 
        # NOTE: this is question specific
        for ii in range(1, n_columns+1):
            column = f'{output_columns}{ii:02}'
            possible_code = row[column]
            if possible_code is None:
                continue
            else:
                possible_code = possible_code.strip(' ')
                # don't include the 97s - this is what we want to replace
                if possible_code == '97':
                    continue
                else:
                    idx_option = np.where(code_list==possible_code)[0]
                    if len(idx_option)>0:
                        code_vals[idx_option[0]] = 1

        tmp_df = pd.DataFrame(np.array([response] + code_vals).reshape(1, -1), columns = ['response'] + list(code_list))
        output_df = pd.concat([output_df, tmp_df]).reset_index(drop=True)

    # convert outputs to ints (the np array likes to make them strings)
    output_df.iloc[:, 1:] = output_df.iloc[:, 1:].astype(int)

    return output_df



## QUESTION 22 SPECIFIC

# get extra information about each country (other spellings, nationalities, etc)
def get_country_info(row):
    # Skip rows where 'code' is 88, 99, or 80000
    if row['code'] in [88, 99, 80000]:
        return []
    
    country_name = row['description']
    
    try:
        # Fetch country information
        country = CountryInfo(country_name)
        data = country.info()
        
        # Check if the data is available
        if not data:
            return []
        
        # Extract alternative spellings, capital, demonym and native name of that country
        altSpellings = data.get('altSpellings', [])
        capital = data.get('capital', "")
        demonym = data.get('demonym', "")
        nativeName = data.get('nativeName', "")
        
        # Combine the extracted details into a single string
        # NOTE: this might be adding too many, focus on just the demonyms/capitals for now
        
        # description_extended = altSpellings + [capital, demonym, nativeName]
        description_extended = altSpellings + [demonym]

        # exclude country codes (too short to be useful)
        description_extended = [
            x for x in description_extended 
            if (len(x) > 2 or x=='US' or x=='UK')
            ]

        return description_extended
    
    except KeyError:  # Handle countries not found in the countryinfo package
        return []
    

# reshape the dataframe so each row is a continent/person response
# instead of each row having a person/all continents
def reshape_df(df_open):
    # do this piece wise to deal with weird shape 
    df_reshaped = pd.DataFrame(
        columns = ['id', 'cycle', 'q22ances', 'aq22ances'] + 
                    [f'q22ances_c0{ii}' for ii in range(1, 6)] +
                    ['origin']
    )

    for jj in range(1, 5+1):
        cols = ['id', 'cycle', f'q22ances{jj}', f'aq22ances{jj}'] + [f'q22ances_c{(jj-1)*5 + ii:02}' for ii in range(1 ,6)]
        df_tmp = df_open.loc[:, cols]
        df_tmp['origin'] = jj
        df_tmp.columns = df_reshaped.columns
        df_reshaped = pd.concat([df_reshaped, df_tmp])

    # Filtering rows where q22ances and aq22ances are not None
    df_reshaped = df_reshaped[df_reshaped['q22ances'].notna() & df_reshaped['aq22ances'].notna()]
    df_reshaped = df_reshaped.sort_values(by='id')
    return df_reshaped


# modify long form code df to include extra nationality info
def get_long_form_codes_q22(code_df_long_tmp):

    long_desc_dict = {
    'libyan arab jamahiriya': 'libya',
    'republic of the congo': 'congo',
    'democratic republic of the congo': 'drc',
    'united republic of tanzania': 'tanzania',
    'republic of south africa': 'south africa',
    'plurinational state of bolivia': 'bolivia',
    'bolivarian republic of venezuela': 'venezuela',
    'macao special administrative region': 'macao',
    "democratic people's republic of korea": 'north korea',
    'hong kong special administrative region': 'hong kong',
    "lao people's democratic republic": 'laos',
    'syrian arab republic': 'syria',
    'republic of macedonia': 'macedonia',
    'federated states of micronesia': 'micronesia'   
}
    
    # shorten some long codes to be more useful
    code_df_long_tmp['description'] = (
        code_df_long_tmp['description']
        .apply(lambda x: x if x not in long_desc_dict else long_desc_dict[x])
    )

    code_dict_long = { 'code': [], 'code_desc': [], 'description': [] }
    for idx, row in code_df_long_tmp.iterrows():

        # get the new codes for each country (nationalities, alternate spellings, etc)
        code = row.code
        code_desc = row.code_desc
        description = row.description

        description_extended = get_country_info(row)
        description_full = [description] + [x.lower() for x in description_extended]
        description_full = [*set(description_full)]

        n_desc = len(description_full)

        if n_desc==0:
            continue

        # append to dictionary
        code_dict_long['code'].extend([code]*n_desc)
        code_dict_long['code_desc'].extend([code_desc]*n_desc)
        code_dict_long['description'].extend(description_full)

    code_df_long = pd.DataFrame(code_dict_long)

    # get rid of duplicate rows
    code_df_long = code_df_long.drop_duplicates().reset_index(drop=True)

    # get rid of long descriptions
    # code_df_long = code_df_long[code_df_long.description.str.len()<20].reset_index(drop=True)

    return code_df_long


# convert the big long inputs to a condensed version for q22. 
# model works better this way
def convert_input(input_df):
    tmp = (
        input_df
        .reset_index()
        .melt(id_vars=['index', 'response'])
        .assign(code = lambda x: x.variable.apply(lambda x: x.split('_')[0]))
        .assign(value = lambda x: pd.to_numeric(x['value'], errors='coerce'))  # Convert to numeric
        .groupby(['index', 'response', 'code'], group_keys=False)
        .apply(lambda x: x.nlargest(4, 'value'))
        .groupby(['index', 'response', 'code'])
        .value.mean()
        .reset_index()
        .sort_values(by=['index', 'code'])
        .pivot_table(index=['index', 'response'], columns=['code'])
    )
    
    tmp.columns = [x[1] for x in tmp.columns]
    tmp = tmp.reset_index().drop('index', axis=1)
    return tmp