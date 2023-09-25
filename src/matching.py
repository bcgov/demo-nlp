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
# Functions to aid in questions                       #
# using simplified matching                           #
#                                                     #
#######################################################

import html
import string
import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
import warnings
import os
import nltk
from nltk.corpus import stopwords
from collections import Counter
from autocorrect import Speller

warnings.simplefilter(action='ignore')


# reshape the dataframe for question 34
def melt_df(df_open):
    # pivot df to be one row per response, then drop all empty rows 
    end_chars = string.ascii_lowercase
    n_columns = 10
    df = pd.melt(
        df_open, 
        id_vars = ['id', 'cycle'], 
        value_vars = [f'aq34culture_{end_chars[idx]}' for idx in range(n_columns)]
    )

    df = df.drop('variable', axis=1)
    df.columns = ['id', 'cycle', 'response']
    df = df[df.response.str.len() > 0].reset_index(drop=True)
    df.response = df.response.astype(str)

    return df


# reshape the dataframe for question 30
def reshape_df(df_open):
    # do this piece wise to deal with weird shape 
    cols_to_pivot = [
        'aq30religbox01buddhist',
        'aq30religbox02christian',
        'aq30religbox03hindu',
        'aq30religbox04jewish',
        'aq30religbox05muslim',
        'aq30religbox06sikh',
        'aq30religbox07tradindig',
        'aq30religbox08another',
        'aq30religbox10no'        
        ]
    
    df_reshaped = pd.DataFrame(
        columns = ['id', 'cycle', 'q30relig', 'origin', 'response']
    )

    for jj in range(1, 10):
        cols = ['id', 'cycle', 'q30relig', cols_to_pivot[jj-1]]
        df_tmp = df_open.loc[:, cols]
        df_tmp['response'] = df_tmp[cols_to_pivot[jj-1]]

        # question 9 has no response, skip to 10 as origin string 
        if jj == 9:
            jj+=1

        df_tmp['origin'] = str(jj)
        df_tmp = df_tmp[df_reshaped.columns]
        df_reshaped = pd.concat([df_reshaped, df_tmp])

    # Filtering rows where responses are not None
    df_reshaped = df_reshaped[
        (df_reshaped['q30relig'].notna()) & 
        (df_reshaped['response'].notna()) &
        (df_reshaped['response'].str.len()>0)
        ]
    df_reshaped = df_reshaped.sort_values(by='id').reset_index(drop=True)
    return df_reshaped


# translate
def get_translation(text, skip=True):

    if skip:
        return text, 0
    
    text = text.strip()
    
    url_params = {"tl": "en", "sl": "auto", 'q': text, 'format': text}
    
    base_url = "https://translate.google.com/m"
    
    response = requests.get(base_url, params=url_params, verify=False)

    if response.status_code == 429:
        print('Too many requests')
        return text, response.status_code

    if response.status_code > 299 or response.status_code < 200:
        print('Request Failed')
        return text, response.status_code

    soup = BeautifulSoup(response.text, "html.parser")

    element = soup.find("div", {"class": "t0"})

    status_code = response.status_code
    response.close()

    if not element:
        element = soup.find("div", {"class": "result-container"})
        if not element:
            print('Translation not found')
            return text, status_code
            
    if element.get_text(strip=True) == text.strip():
        to_translate_alpha = "".join(
            ch for ch in text.strip() if ch.isalnum()
        )
        translated_alpha = "".join(
            ch for ch in element.get_text(strip=True) if ch.isalnum()
        )
        if (
            to_translate_alpha
            and translated_alpha
            and to_translate_alpha == translated_alpha
        ):
            
            if "hl" not in url_params:
                return text.strip(), status_code
                
            return get_translation(text)

    else:
        return element.get_text(strip=True), status_code
    
    return 'test', 0

# exact matching
def exact_match(word, code):
    word = word.lower()
    code = code.lower()
    return word == code

# partial matching
def partial_match(word, code):
    word = word.lower()
    code = code.lower()
    match = False
    if word != code:
        if re.search(r'\b' + code + r'\b', word):
            match = True

    return match

# some matching partially - remove as unlikely matches
def likely_matches(match_codes):
    codes = [x.strip(' ').lower() for x in re.split('[,]', match_codes) if len(x)>0]
    sorted_codes = sorted(codes, key=len)
    n_codes = len(sorted_codes)
    likely_matches = []
    for ii in range(n_codes):
        keep = True
        smaller_code = sorted_codes[ii]
        for jj in range(ii+1, n_codes):
            longer_code = sorted_codes[jj]
            
            if smaller_code in longer_code:
                keep = False
                break

        if keep:
            likely_matches.append(smaller_code.title())

    return ', '.join(likely_matches)


# combined into one
def do_the_things(x, spell, code_list, translate_all = False):

    # step 1: remove spaces, escape html, spell check
    cleaned = spell(html.unescape(x.strip(' ')))

    # step 2: translate (slow)
    if translate_all:
        translated, response_code = get_translation(cleaned, skip=False)

    else:
        if x[0]=='&':
            translated, response_code = get_translation(cleaned, skip=False)
        else:
            translated, response_code = get_translation(cleaned, skip=True)

    # for each code, check if there is an exact or partial match
    exact_match_codes = ''
    partial_match_codes = ''
    has_exact = False
    has_partial = False
    for code in code_list:

        if exact_match(translated, code):
            has_exact = True
            exact_match_codes += code + ', '

        if partial_match(translated, code):
            has_partial = True
            partial_match_codes += code + ', '

    exact_match_codes = exact_match_codes.strip(' ').strip(',')
    partial_match_codes = partial_match_codes.strip(' ').strip(',')

    likely_match_codes = likely_matches(exact_match_codes + ', ' + partial_match_codes)

    return x, cleaned, translated, response_code, has_exact, has_partial, exact_match_codes, partial_match_codes, likely_match_codes


# tokenize and count word frequencies of those with no match
def tokenize_and_count_word_frequencies(sentences):
    # Load the NLTK English stop words
    stop_words = set(stopwords.words('english'))

    # Initialize a counter for word frequencies
    word_frequencies = Counter()

    for sentence in sentences:
        # Tokenize the sentence into words
        words = nltk.word_tokenize(sentence.lower())  # Convert to lowercase

        # Remove stop words and non-alphabetic words
        words = [word for word in words if word.isalpha() and word not in stop_words]

        # Update the word frequencies
        word_frequencies.update(words)

    return word_frequencies


# create a speller
def create_speller(code_list, extra_words):
    spell = Speller()

    # get a list of all words that are directly in the code words 
    all_words = []
    for word in code_list:
        words = re.split(r"\sand\s|[,;()/\r\n\s'-]+", word)
        for x in words:
            if len(x) > 0:
                all_words.append(x)
                
    # add additional words that are not inaccurate 
    words = extra_words
    for word in all_words + words:

        for x in [word, word.upper(), word.lower()]:
            if x in spell.nlp_data:
                continue
                
            spell.nlp_data[word] = 1_000_000
            spell.nlp_data[word.upper()] = 1_000_000
            spell.nlp_data[word.lower()] = 1_000_000

    return spell


# split the languages in the codes table
def split_languages(description):
    code_list = []
    codes = re.split(r'\sand\s|languages|n\.i\.e\.|n\.i\.e|n\.o\.s\.|[,()]+', description)
    for code in codes:
        code = code.strip(' ')
        if re.search('[A-Za-z]+', code):
            code_list.append(code)

    return code_list


# split religions
def split_religions(description):
    code_list = []
    codes = re.split(r'[,()/]+', description)
    for code in codes:
        code = code.strip(' ')
        if re.search('[A-Za-z]+', code):
            code_list.append(code)

    return code_list


# split cultures
def split_cultures(description):
    code_list = []
    codes = re.split(r'[,()/]+', description)
    for code in codes:
        code = code.strip(' ')
        if re.search('[A-Za-z]+', code):
            code_list.append(code)

    return code_list


# produce new language codes dictionary
def update_codes_language(df_codes):
    # for q29, some of the descriptions are hidden in the desc column - pull these out
    df_codes_dict = {
        'q_code': [],
        'qc_desc': []
    }

    for idx, row in df_codes.iterrows():
        q_code = row.q_code
        qc_desc = row.qc_desc

        # roll indigenous bc languages into the same code
        note = row.additional_notes
        if note == 'Roll into 6':
            q_code = '6'

        # add portugalês in manually
        if qc_desc == 'Portuguese':
            df_codes_dict['q_code'].append(q_code)
            df_codes_dict['qc_desc'].append('portugalês')

        # split the qc desc to remove the word 'languages' 
        if qc_desc == 'Indigenous languages in B.C.':
            df_codes_dict['q_code'].append(q_code)
            df_codes_dict['qc_desc'].append(qc_desc)

        else:
            if qc_desc is not None:
                code_list = split_languages(qc_desc)
                for code in code_list:
                    df_codes_dict['q_code'].append(q_code)
                    df_codes_dict['qc_desc'].append(code)

        # get the responses from the optional row as well 
        qc_optional = row.qc_desc_notes
        if not pd.isnull(qc_optional):
            code_list = split_languages(qc_optional)
            for code in code_list:
                df_codes_dict['q_code'].append(q_code)
                df_codes_dict['qc_desc'].append(code)
                

    # add some extras
    df_codes_dict['q_code'].append('1222101')
    df_codes_dict['qc_desc'].append('ASL')

    # remove duplicates
    df_codes_updated = pd.DataFrame(df_codes_dict)
    df_codes_updated = df_codes_updated.groupby('qc_desc').first().reset_index()

    return df_codes_updated


# produce new religion codes dictionary
def update_codes_religion(df_codes):
    # for q30, some of the descriptions are hidden in the desc column - pull these out
    df_codes_dict = {
        'q_code': [],
        'qc_desc': [],
        'main_code': []
    }

    for idx, row in df_codes.iterrows():
        q_code = row.q_code
        qc_desc = row.qc_desc

        # find the code group we are working with
        if len(q_code)==1:
            main_code = q_code

        else:
            sub_code = q_code[0:2]
            if (sub_code == '10') or (sub_code == '88') or (sub_code == '99'):
                main_code = sub_code 
            else:
                main_code = q_code[0]

        # don't update the wording on the main categories
        if len(q_code) == 1:
            df_codes_dict['q_code'].append(q_code)
            df_codes_dict['qc_desc'].append(qc_desc)
            df_codes_dict['main_code'].append(main_code)

        else:
            if qc_desc is not None:
                code_list = split_religions(qc_desc)
                for code in code_list:
                    df_codes_dict['q_code'].append(q_code)
                    df_codes_dict['qc_desc'].append(code)
                    df_codes_dict['main_code'].append(main_code)

        # get the responses from the optional row as well 
        qc_optional = row.qc_desc_notes
        if not pd.isnull(qc_optional):
            code_list = split_religions(qc_optional)
            for code in code_list:
                df_codes_dict['q_code'].append(q_code)
                df_codes_dict['qc_desc'].append(code)
                df_codes_dict['main_code'].append(main_code)
                
    # remove duplicates
    df_codes_updated = pd.DataFrame(df_codes_dict)
    df_codes_updated = df_codes_updated.groupby('qc_desc').first().reset_index().sort_values(by='q_code').reset_index(drop=True)

    return df_codes_updated


# produce new culture codes dictionary
def update_codes_culture(df_codes):
    # for q34, some of the descriptions are hidden in the desc column - pull these out
    df_codes_dict = {
        'q_code': [],
        'qc_desc': []
    }

    for idx, row in df_codes.iterrows():
        q_code = row.q_code
        qc_desc = row.qc_desc

        if qc_desc is not None:

            # always add in the actual description as is, because these were 
            # displayed to people as they typed
            df_codes_dict['q_code'].append(q_code)
            df_codes_dict['qc_desc'].append(qc_desc)

            # also do splits to allow for matches to things in parentheses
            code_list = split_cultures(qc_desc)
            for code in code_list:
                df_codes_dict['q_code'].append(q_code)
                df_codes_dict['qc_desc'].append(code)

        # get the responses from the optional row as well 
        qc_optional = row.qc_desc_notes
        if not pd.isnull(qc_optional):
            code_list = split_languages(qc_optional)
            for code in code_list:
                df_codes_dict['q_code'].append(q_code)
                df_codes_dict['qc_desc'].append(code)


    # add some extras - accents not handled well in database 
    df_codes_dict['q_code'].append('1133')
    df_codes_dict['qc_desc'].append('Québécois')
    df_codes_dict['q_code'].append('1133')
    df_codes_dict['qc_desc'].append('Quebecois')

    # remove duplicates
    df_codes_updated = pd.DataFrame(df_codes_dict)
    df_codes_updated = df_codes_updated.groupby('qc_desc').first().reset_index()

    return df_codes_updated


# print statistics for latest run
def print_stats(clean_df):
    exact = clean_df.exact_match.sum()
    n_rows = clean_df.shape[0]
    partial_no_exact = clean_df[~clean_df.exact_match].partial_match.sum()
    n_rows_no_exact = clean_df[~clean_df.exact_match].shape[0]
    print(f'Exact Matches: {exact:,}/{n_rows:,} ({exact/n_rows:.0%})')
    print(f'Partial Matches: {partial_no_exact:,}/{n_rows_no_exact:,} ({partial_no_exact/n_rows_no_exact:.0%})')
    print(f'Leftover: {n_rows - exact - partial_no_exact:,}/{n_rows:,} ({(n_rows - exact - partial_no_exact)/n_rows:.0%})')


# trasform the entire dataframe for languages
def transform_languages(df, df_codes_updated, spell):

    clean_dict = {
    'id': [],
    'cycle': [],
    'response': [], 
    'cleaned': [],
    'translated': [],
    'translation_code': [],
    'exact_match': [],
    'partial_match': [],
    'exact_match_codes': [],
    'partial_match_codes': [],
    'likely_match_codes': [],
    'q29lang_c01': [],
    'q29lang_c02': [],
    'q29lang_c03': [],
    'q29lang_c04': []
}

    n_rows = df.shape[0]

    code_list = df_codes_updated.qc_desc.values

    for idx, row in df.iterrows():

        x = row.response
        id = row.id
        cycle = row.cycle
        (response, 
        cleaned, translated, response_code, 
        has_exact, has_partial, 
        exact_match_codes, partial_match_codes, likely_match_codes) = do_the_things(x, spell, code_list, translate_all = False)

        clean_dict['id'].append(id)
        clean_dict['cycle'].append(cycle)
        clean_dict['response'].append(response)    
        clean_dict['cleaned'].append(cleaned)
        clean_dict['translated'].append(translated)
        clean_dict['translation_code'].append(response_code)
        clean_dict['exact_match'].append(has_exact)
        clean_dict['partial_match'].append(has_partial)
        clean_dict['exact_match_codes'].append(exact_match_codes)
        clean_dict['partial_match_codes'].append(partial_match_codes)
        clean_dict['likely_match_codes'].append(likely_match_codes)

        # code version of new codes 
        new_codes = []
        split_codes = likely_match_codes.split(', ')
        for code in split_codes:
            if code != '':
                new_codes.append(df_codes_updated[df_codes_updated.qc_desc.str.lower() == code.lower()].q_code.values[0])

        # remove 97 from list of codes included
        existing_codes = []
        for ii in range(1,5):
            col_name = f'q29lang_c0{ii}'
            val = row[col_name]
            if not pd.isnull(val):
                if val!='97':
                    existing_codes.append(val)

        # add new codes into code columns
        all_codes = existing_codes + new_codes 
        for jj in range(1, 5):
            col_name = f'q29lang_c0{jj}'
            if jj <= len(all_codes):
                clean_dict[col_name].append(all_codes[jj-1])
            else:
                clean_dict[col_name].append(None)
        
        pct_done = int(round(100*(idx+1)/n_rows))
        print_line = f'{idx+1:07,}/{n_rows:07,}   |' + '-'*(pct_done) + '>' + ' '*(100-pct_done) + '|'
        print(print_line, end = '\r')

    clean_df = pd.DataFrame(clean_dict)
    # make sure we are in the right order
    clean_df = clean_df[
        [
            'id', 
            'cycle',
            'response',
            'cleaned',
            'translated',
            'translation_code',
            'exact_match',
            'partial_match',
            'exact_match_codes',
            'partial_match_codes',
            'likely_match_codes',
            'q29lang_c01',
            'q29lang_c02',
            'q29lang_c03',
            'q29lang_c04',
        ]
    ]

    return clean_df


# trasform the entire dataframe for relgions
def transform_religions(df, df_codes_updated, spell):

    clean_dict = {
    'id': [],
    'cycle': [],
    'q30relig': [], 
    'origin': [],
    'response': [], 
    'cleaned': [],
    'translated': [],
    'translation_code': [],
    'exact_match': [],
    'partial_match': [],
    'exact_match_codes': [],
    'partial_match_codes': [],
    'likely_match_codes': [],
    'likely_match_numeric': [],
    'likely_match_groups': []
}

    n_rows = df.shape[0]

    code_list = df_codes_updated.qc_desc.values

    for idx, row in df.iterrows():

        x = row.response
        id = row.id
        cycle = row.cycle
        q30 = row.q30relig
        origin = row.origin
        
        (response, 
        cleaned, translated, response_code, 
        has_exact, has_partial, 
        exact_match_codes, partial_match_codes, likely_match_codes) = do_the_things(x, spell, code_list, translate_all = False)

        clean_dict['id'].append(id)
        clean_dict['cycle'].append(cycle)
        clean_dict['q30relig'].append(q30)
        clean_dict['origin'].append(origin)
        clean_dict['response'].append(response)    
        clean_dict['cleaned'].append(cleaned)
        clean_dict['translated'].append(translated)
        clean_dict['translation_code'].append(response_code)
        clean_dict['exact_match'].append(has_exact)
        clean_dict['partial_match'].append(has_partial)
        clean_dict['exact_match_codes'].append(exact_match_codes)
        clean_dict['partial_match_codes'].append(partial_match_codes)
        clean_dict['likely_match_codes'].append(likely_match_codes)

        # code version of new codes 
        new_codes = []
        main_codes = []
        split_codes = likely_match_codes.split(', ')
        for code in split_codes:
            if code != '':
                new_codes.append(df_codes_updated[df_codes_updated.qc_desc.str.lower() == code.lower()].q_code.values[0])
                main_codes.append(df_codes_updated[df_codes_updated.qc_desc.str.lower() == code.lower()].main_code.values[0])

        # get unique lists of new codes and main codes 
        new_codes = list(set(new_codes))
        main_codes = list(set(main_codes))

        new_codes_str = ', '.join(new_codes)
        main_codes_str = ', '.join(main_codes)
        
        clean_dict['likely_match_numeric'].append(new_codes_str)
        clean_dict['likely_match_groups'].append(main_codes_str)
        
        pct_done = int(round(100*(idx+1)/n_rows))
        print_line = f'{idx+1:07,}/{n_rows:07,}   |' + '-'*(pct_done) + '>' + ' '*(100-pct_done) + '|'
        print(print_line, end = '\r')

    clean_df = pd.DataFrame(clean_dict)

    # make sure we are in the right order
    clean_df = clean_df[
        [
            'id',
            'cycle',
            'q30relig', 
            'origin',
            'response', 
            'cleaned',
            'translated',
            'translation_code',
            'exact_match',
            'partial_match',
            'exact_match_codes',
            'partial_match_codes',
            'likely_match_codes',
            'likely_match_numeric',
            'likely_match_groups'
        ]
    ]

    return clean_df


# trasform the entire dataframe for cultures
def transform_cultures(df, df_codes_updated, spell):
    clean_dict = {
    'id': [],
    'cycle': [],
    'response': [], 
    'cleaned': [],
    'translated': [],
    'translation_code': [],
    'exact_match': [],
    'partial_match': [],
    'exact_match_codes': [],
    'partial_match_codes': [],
    'likely_match_codes': []
}

    n_rows = df.shape[0]

    code_list = df_codes_updated.qc_desc.values

    for idx, row in df.iterrows():

        x = row.response
        id = row.id
        cycle = row.cycle
        (response, 
        cleaned, translated, response_code, 
        has_exact, has_partial, 
        exact_match_codes, partial_match_codes, likely_match_codes) = do_the_things(x, spell, code_list)

        clean_dict['id'].append(id)
        clean_dict['cycle'].append(cycle)
        clean_dict['response'].append(response)    
        clean_dict['cleaned'].append(cleaned)
        clean_dict['translated'].append(translated)
        clean_dict['translation_code'].append(response_code)
        clean_dict['exact_match'].append(has_exact)
        clean_dict['partial_match'].append(has_partial)
        clean_dict['exact_match_codes'].append(exact_match_codes)
        clean_dict['partial_match_codes'].append(partial_match_codes)
        clean_dict['likely_match_codes'].append(likely_match_codes)
        
        pct_done = int(round(100*(idx+1)/n_rows))
        print_line = f'{idx+1:07,}/{n_rows:07,}   |' + '-'*(pct_done) + '>' + ' '*(100-pct_done) + '|'
        print(print_line, end = '\r')

    clean_df = pd.DataFrame(clean_dict)
    # make sure we are in the right order
    clean_df = clean_df[
        [
            'id', 
            'cycle',
            'response',
            'cleaned',
            'translated',
            'translation_code',
            'exact_match',
            'partial_match',
            'exact_match_codes',
            'partial_match_codes',
            'likely_match_codes'
        ]
    ]

    return clean_df