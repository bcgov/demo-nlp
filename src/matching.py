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


def split_cultures(description):
    code_list = []
    codes = re.split(r'[,()/]+', description)
    for code in codes:
        code = code.strip(' ')
        if re.search('[A-Za-z]+', code):
            code_list.append(code)

    return code_list