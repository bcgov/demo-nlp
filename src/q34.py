from autocorrect import Speller
import html
import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
import warnings
import os
warnings.simplefilter(action='ignore')

# translate
def get_translation(text):
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
        if re.search(code, word):
            match = True

    return match

# some matching partially - remove as unlikely matches
def likely_matches(match_codes):
    codes = [x.strip(' ') for x in re.split('[,]', match_codes) if len(x)>0]
    sorted_codes = sorted(codes, key=len)
    n_codes = len(sorted_codes)
    likely_matches = []
    for ii in range(n_codes):
        keep = True
        smaller_code = sorted_codes[ii]
        for jj in range(ii+1, n_codes):
            longer_code = sorted_codes[jj]
            
            if smaller_code in longer_code:
                print(smaller_code, longer_code)
                keep = False
                break

        if keep:
            likely_matches.append(smaller_code)

    return ', '.join(likely_matches)


# combined into one
def do_the_things(x, spell, code_list):

    # step 1: remove spaces, escape html, spell check
    cleaned = spell(html.unescape(x.strip(' ')))

    # step 2: translate (slow)
    # translated, response_code = get_translation(cleaned)
    if x[0]=='&':
        cleaned = get_translation(cleaned)[0]

    # for each code, check if there is an exact or partial match
    exact_match_codes = ''
    partial_match_codes = ''
    has_exact = False
    has_partial = False
    for code in code_list:

        if exact_match(cleaned, code):
            has_exact = True
            exact_match_codes += code + ', '

        if partial_match(cleaned, code):
            has_partial = True
            partial_match_codes += code + ', '

    exact_match_codes = exact_match_codes.strip(' ').strip(',')
    partial_match_codes = partial_match_codes.strip(' ').strip(',')

    likely_match_codes = likely_matches(exact_match_codes + ', ' + partial_match_codes)

    return x, cleaned, has_exact, has_partial, exact_match_codes, partial_match_codes, likely_match_codes
