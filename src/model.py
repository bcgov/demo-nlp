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
# Functions to aid in creating/using a model          #
#                                                     #
#######################################################

# IMPORTS 

# system stuff
import os
import sys
import shutil

# modeling
from sklearn.ensemble import RandomForestClassifier
import joblib

# standard
import numpy as np
import pandas as pd

# our stuff
from .preprocess import *
from .connect import *

# create classifier
def create_model(input_df, output_df, verbose=True, **kwargs):
    if verbose:
        verbose = 1
    else:
        verbose = 0
    clf = RandomForestClassifier(random_state = 0, verbose=1, **kwargs)
    clf.fit(input_df, output_df)

    return clf

# save classifier
# must also save the code df long so that it matches exactly what was used
def save_model(cred_path, model_base_path, model, code_df_long):
    model_path = get_model_path(cred_path, model_base_path)
    create_model_files = False
    if os.path.isdir(model_path):
        if len(os.listdir(model_path))>1:
            option = input(f'Model already exists in directory {model_path}. Overwrite? (y)/n: ')
            option = option.lower()
            if option == '' or option == 'y':
                create_model_files = True
                shutil.rmtree(model_path)
            else:
                print('Model not saved.')
    else:
        create_model_files = True

    if create_model_files:
        os.makedirs(model_path)
        joblib.dump(model, os.path.join(model_path, 'model.joblib'))
        code_df_long.to_csv(os.path.join(model_path, 'code_df_long.csv'), index=False)


# load classifier
# must also load the code df long so that it matches exactly what was used 
def load_model(cred_path, model_base_path):
    model_path = get_model_path(cred_path, model_base_path)
    model = joblib.load(os.path.join(model_path, 'model.joblib'))
    code_df_long = pd.read_csv(os.path.join(model_path, 'code_df_long.csv'), dtype='string')
    return model, code_df_long


# create validation matrix/final table to export back to database
def produce_results(
        df, 
        input_df, 
        output_df, 
        clf,
        output_columns,
        n_columns,
        question = 'Q32',
        threshold = 0.5,
        tentative_lower = 0.25,
        tentative_upper = 0.75,
        delimiter = 'μ',
        verbose = True
        ):

    # create inputs for model
    actual_input_df = input_df.drop('response', axis=1).astype(int)
    actual_output_df = output_df.drop('response', axis=1).astype(int)

    # get outputs from model
    # Use raw data to test the model
    test_out = clf.predict_proba(actual_input_df)

    # this removes the instances where nothing was predicted for a category
    for idx, item in enumerate(test_out):
        if item.shape[1] == 1:
            test_out[idx] = np.hstack((test_out[idx], 0*test_out[idx]))

    test_out = [x[:, 1] for x in test_out]
    test_out = np.array(test_out).T
    test_out_df = pd.DataFrame(columns = actual_output_df.columns, data= test_out)

    # set up output metrics
    n_rows = actual_output_df.shape[0]

    results_dict = {f'{output_columns}{nn:02}': [] for nn in range(1, n_columns+1)}

    results_dict['match'] = []
    results_dict['original_matched'] = []
    results_dict['extra_categories'] = []
    results_dict['n_original_categories'] = []
    results_dict['n_model_categories'] = []
    results_dict['tentative_categories'] = []

    # add extra flags for Q22
    if question.lower() == 'q22':
        results_dict['outside_continent'] = []
        results_dict['inside_continent'] = []

    for ii in range(n_rows):

        if verbose:
            pct_done = int(100*(ii+1)/n_rows)
            print_str = f'{ii+1:05}/{n_rows}' + '  |' + '-'*pct_done + '>' + ' '*(100-pct_done-1) + '|'
            print(print_str, end='\r')

        y = actual_output_df.iloc[ii, :]
        y_pred = test_out_df.iloc[ii, :]

        results_dict['match'].append(exact_match(y, y_pred, threshold))
        results_dict['original_matched'].append(pct_of_original_matched(y, y_pred, threshold))
        results_dict['extra_categories'].append(num_extra_categories(y, y_pred, threshold))
        results_dict['n_original_categories'].append(num_categories(y, threshold))
        results_dict['n_model_categories'].append(num_categories(y_pred, threshold))
        results_dict['tentative_categories'].append(tentative_categories(y_pred, tentative_lower, tentative_upper, delimiter))

        # add extra flags for Q22
        if question.lower() == 'q22':
            category = str(df.iloc[ii, :].origin)
            results_dict['outside_continent'].append(outside_continent(y_pred, threshold, category))
            results_dict['inside_continent'].append(inside_continent(y_pred, threshold, category))

        all_cats = list_categories(y, y_pred, threshold)
        n_cats = len(all_cats)
        for jj in range(1, n_columns+1):
            if jj > n_cats:
                results_dict[f'{output_columns}{jj:02}'].append(None)
            else:
                results_dict[f'{output_columns}{jj:02}'].append(all_cats[jj-1])

    drop_columns = [f'{output_columns}{kk:02}' for kk in range(1, n_columns+1)]  
    results_df = df.drop(
        columns=drop_columns
        ).merge(pd.DataFrame(results_dict), left_index=True, right_index=True)

    return results_df


# list outputs for a single sentence 
def list_classes(
        sentence, 
        code_df_long, 
        clf, 
        truncate_inputs = False,
        top_n = 10, 
        min_pct = 0.05, 
        spellcheck = True
        ):

    # get the code/code descriptions
    code_df = code_df_long.groupby(['code', 'code_desc']).count().reset_index()
    code_list = code_df_long.code.unique()

    # use spell check if requested
    if spellcheck:
        corrected_sentence = correct_spelling(sentence)
    else:
        corrected_sentence = sentence
    
    tmp = get_scores(corrected_sentence, code_df_long, as_df=True)
    cols = list(tmp.col_id.values)
    tmp = tmp.pivot_table(columns=['col_id']).reset_index(drop=True).rename_axis(None, axis=1)
    tmp = tmp[cols]

    # Q22 uses a slightly different version of inputs, so modify here if necessary
    if truncate_inputs:
        tmp['response'] = corrected_sentence
        tmp = convert_input(tmp).drop('response', axis=1)
    
    test_out = clf.predict_proba(tmp)
    for idx, item in enumerate(test_out):
        if item.shape[1] == 1:
            test_out[idx] = np.hstack((test_out[idx], 0*test_out[idx]))

    test_out = [x[:, 1] for x in test_out]
    test_out = np.array(test_out).T

    predictions = test_out[0]
    ordered_idx = np.argsort(predictions)[::-1]
    print()
    print(f'TOP MATCHES FOR: {sentence}')
    if spellcheck:
        print(f'CORRECTED TO:    {corrected_sentence}')
        
    print()
    for counter, idx in enumerate(ordered_idx):
        if counter>=top_n:
            break
        else:
            prob = predictions[idx]

            if prob < min_pct:
                break
                
            code = code_list[idx]
            desc = code_df.loc[code_df['code'] == code, 'code_desc'].values[0]
            print(f'{prob:0.2%} ({code})')
            print(desc)
            print()


# helper functions for the results dataframe
# exact matches
def exact_match(y, y_pred, threshold):
    y_pred = (y_pred>threshold)*1
    if (y == y_pred).all():
        return 1
    else:
        return 0


# percent of the original categories that got correctly matched 
def pct_of_original_matched(y, y_pred, threshold):
    y_pred = (y_pred>threshold)*1
    y_loc = np.where(y==1)[0]
    yp_loc = np.where(y_pred==1)[0]
    
    c = 0
    for kk in yp_loc:
        if kk in y_loc:
            c+=1

    if len(y_loc) == 0:
        return 1
    else:
        return c / len(y_loc)


# number of extra categories that got categorized
def num_extra_categories(y, y_pred, threshold):
    y_pred = (y_pred>threshold)*1
    y_loc = np.where(y==1)[0]
    yp_loc = np.where(y_pred==1)[0]
    
    c = 0
    for kk in yp_loc:
        if kk not in y_loc:
            c+=1
    return c


# number of categories total
def num_categories(y, threshold):
    y = (y>threshold)*1
    y_loc = np.where(y==1)[0]
    return len(y_loc)


# any categories in a 'tentative' range
def tentative_categories(y_pred, lower, upper, delimiter='μ'):
    tentative_list = list(y_pred[((y_pred>lower) & (y_pred<upper))].index)
    if len(tentative_list) == 0:
        tentative_str = None
    else:
        tentative_str = delimiter.join(tentative_list)
    return tentative_str


# extra q22 flags
# flags if the model predicts a sub-region outside the continent group
def outside_continent(y_pred, threshold, category):
    y_pred = (y_pred>threshold)*1
    subgroups = list(y_pred[y_pred==1].index)

    has_outer = 0
    for subgroup in subgroups:
        if str(subgroup[0]) != str(category):
            has_outer = 1
            break

    return has_outer


# flags if at least one sub-regions is inside the continent group
def inside_continent(y_pred, threshold, category):

    y_pred = (y_pred>threshold)*1
    subgroups = list(y_pred[y_pred==1].index)

    has_inner = 0
    for subgroup in subgroups:
        if str(subgroup[0]) == str(category):
            has_inner = 1
            break

    return has_inner


# list of all categories, including those from the mc
def list_categories(y, y_pred, threshold):
    y_pred = (y_pred>threshold)*1
    y_cats = list(y[y==1].index)
    y_pred_cats = list(y_pred[y_pred==1].index)

    all_cats = y_cats
    for cat in y_pred_cats:
        if cat in all_cats:
            continue
        else:
            all_cats.append(cat)

    return all_cats
