# TODO: insert copyright code 

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

# nlp stuff
from fuzzywuzzy import fuzz
from autocorrect import Speller


# split a list of descriptor words into a list 
def split_description(description):

    # check for NULLs
    if description is None:
        return []
        
    # split string based on comma delimiters, as well as words in brackets
    desc_list = re.split(r'\sand\s|\sor\s|[,()\r\n]+', description)

    # lower case, remove extra characters and remove spaces
    desc_list = [x.lower().replace('"', '').replace('_', '').strip(' ') for x in desc_list]

    # remove descriptors that are empty
    desc_list = [x for x in desc_list if x!='']

    return desc_list


# create a long form codes dataframe. one line per descriptor word
def get_long_form_codes(code_df):
    code_dict_long = { 'code': [], 'code_desc': [], 'description': [] }

    for idx, row in code_df.iterrows():
        code = row.q_code
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
def get_outputs_wide(df, response_column, code_df_long):
    code_list = code_df_long.code.unique()

    output_df = pd.DataFrame(columns = ['response'] + list(code_list))

    for idx, row in df.iterrows():
        response = row[response_column]
        code_vals = [0]*len(code_list)
        # cycle through all the 
        # NOTE: this is question specific
        for ii in range(1,17):
            column = f'q32race_c{ii:02}'
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