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
# Functions to aid in creating synthetic data         #
#                                                     #
#######################################################

# IMPORTS 
# system stuff
import random
import itertools

# standard stuff
import pandas as pd
import numpy as np

# our own tools
from .preprocess import *


# create synthetic data set #1
# this section will create synthetic data that matches a single category based on available phrases 
# and will add enough to the training dataset so that each category is equally represented
def create_single_phrase_synthetic(
        output_df, 
        input_columns, 
        output_columns, 
        code_df_long,
        n_per_category = None,
        use_given = True,
        verbose = True
        ):

    # make sure code counts are sorted
    code_counts = code_counts = output_df.drop('response', axis=1).sum().sort_values(ascending=False)
    n_codes = len(code_counts)
    max_counts = code_counts.values[0]

    # if n_per_category not given, use max counts
    if n_per_category is None:
        n_per_category = max_counts

    # get list of codes
    code_list = code_df_long.code.unique()

    # initalize dataframes for output
    extra_output_df = pd.DataFrame(columns = output_columns)
    extra_input_df = pd.DataFrame(columns = input_columns)

    count = 0
    for idx, val in code_counts.items():

        count+=1
        if verbose:
            print()
            print_string = f'{count:02}/{n_codes:02} -- Code: {idx} -- Observations: {val}'
            print(print_string, end='\r')

        # remove the value count if you just want n_per_category more regardless
        if use_given:
            val = val
        else:
            val = 0

        # don't add any more to biggest class 
        if val == n_per_category:
            continue
            
        else:
            if idx=='Human':
                continue
            idx = idx.strip(' ')
            
            # find all words associated with that index
            desc_list = code_df_long[code_df_long.code==idx].description.values
            code_vals = [0]*len(code_list)

            # locate index of this code in code list 
            code_idx = np.where(code_list==idx)[0]
            
            if len(code_idx) == 0:
                continue

            n_more_counts = n_per_category - val

            # randomly select synthetic data
            random_df = pd.DataFrame(columns = ['response'], data = random.choices(desc_list, k=n_more_counts))

            # create outputs
            code_vals = np.zeros((n_more_counts, n_codes))
            code_vals[:, code_idx] = 1
            output_df = pd.DataFrame(columns = list(code_list), data= code_vals).astype(int)
            output_df = random_df.merge(output_df, left_index=True, right_index=True)

            # create inputs
            input_df = get_scores_from_df(random_df, 'response', code_df_long, input_columns)

            # append to extra synthetic df
            extra_output_df = pd.concat([extra_output_df, output_df]).reset_index(drop=True)
            extra_input_df = pd.concat([extra_input_df, input_df]).reset_index(drop=True)

            if verbose:
                print_string = f'{count:02}/{n_codes:02} -- Code: {idx} -- Observations: {val} + {n_more_counts}. Done.'
                print(print_string, end='\r')

    return extra_input_df, extra_output_df


# create synthetic data set # 2
# this section will create synthetic data that matches multiple categories
# category frequecy is guided by the actual frequency of close ended responses
def create_multi_phrase_synthetic(
        output_df,
        df_closed,
        input_columns,
        output_columns,
        code_df_long,
        n_synthetic=200_000,
        verbose=True
):
    
    # Get code list
    code_list = code_df_long.code.unique()

    # Extract existing combinations from test_df
    code_columns = output_df.iloc[:, 1:]
    multi_response_freq_test = output_df[code_columns.sum(axis=1) > 1].drop('response', axis=1).apply(lambda x: tuple(x.index[x == 1]), axis=1)
    multi_response_freq_test = multi_response_freq_test.value_counts().reset_index()
    multi_response_freq_test.columns = ['combination', 'frequency']

    # Extract combinations from df_closed

    # change to generic column name 
    df_closed = df_closed.copy()
    df_closed.columns = ['response']
    df_closed['combination'] = df_closed['response'].apply(lambda x: tuple(x.split('µ')))
    multi_response_freq_closed = df_closed['combination'].value_counts().reset_index()
    multi_response_freq_closed.columns = ['combination', 'frequency']

    # Merge the frequency distributions
    multi_response_freq = pd.concat([multi_response_freq_test, multi_response_freq_closed])
    multi_response_freq = multi_response_freq.groupby('combination').sum().reset_index()
    
    manual_combinations = [
        ('21', '32'), 
        ('42', '14'), 
        ('21', '52'), 
        ('42', '33'), 
        ('31', '43'), 
        ('12', '44'), 
        ('15', '21', '33'), 
        ('11', '12', '13', '14'), 
        ('21', '22', '23', '24'), 
        ('31', '32', '33', '34'), 
        ('41', '42', '43', '44'),
        ('51', '52', '53', '54'),
        ('53', '43', '33', '23'),
        ('51', '41', '31', '21')
        ]
    for combination in manual_combinations:
        existing_rows = multi_response_freq[multi_response_freq['combination'] == combination]
        if existing_rows.empty:
            # If the combination doesn't exist, add a new row
            multi_response_freq = pd.concat(
                [
                    multi_response_freq, 
                    pd.DataFrame({'combination': combination, 'frequency': 10})
                ], 
                ignore_index=True
                )
            
    # Normalize frequency for probability
    multi_response_freq['frequency'] /= multi_response_freq['frequency'].sum()

    # Initialize dataframes
    mixed_output_df = pd.DataFrame(columns=output_columns)
    mixed_input_df = pd.DataFrame(columns=input_columns)

    # initalize a list to hold interim results
    mixed_output_list = []

    # Iterate to create mixed synthetic data
    for jj in range(n_synthetic):

        if verbose:
            pct_done = int(100*(jj+1)/n_synthetic)
            print_str = f'{jj+1:05}/{n_synthetic}' + '  |' + '-'*pct_done + '>' + ' '*(100-pct_done-1) + '|'
            print(print_str, end='\r')

        # Choose a random combination based on frequency
        combination = np.random.choice(multi_response_freq['combination'], p=multi_response_freq['frequency'])
        code_vals = [0] * len(code_list)
        phrase_list = []

        for code in combination:

            code = code.strip(' ')

            # find all words associated with that index
            desc_list = code_df_long[code_df_long.code==code].description.values

            # locate index of this code in code list 
            code_idx = np.where(code_list==code)[0]
            if len(code_idx) == 0:
                continue

            code_vals[code_idx[0]] = 1

            # randomly choose a term from list 
            random_code_phrase = random.choice(desc_list)
            phrase_list.append(random_code_phrase)

        # create outputs
        phrase = ' '.join(phrase_list)
        mixed_output_list.append([phrase] + code_vals)

    if verbose:
        print()
        print('Creating synthetic data outputs... ', end='')
    # Convert to dataframe
    mixed_output_df = pd.DataFrame(columns = output_columns, data=np.array(mixed_output_list))
    mixed_output_df[mixed_output_df.columns[1:]] = mixed_output_df.iloc[:, 1:].astype(int)

    if verbose:
        print('Done.')
        print('Creating synthetic data inputs... ', end='')

    # Get training values using existing get_scores function
    mixed_input_df = get_scores_from_df(mixed_output_df, 'response', code_df_long, input_columns)

    if verbose:
        print('Done.')

    return mixed_input_df, mixed_output_df
