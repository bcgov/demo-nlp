[![Lifecycle:Stable](https://img.shields.io/badge/Lifecycle-Stable-97ca00)](https://github.com/bcgov/repomountie/blob/master/doc/lifecycle-stable.md)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

## demo-nlp
---

### Purpose

Repository to host code and documentation surrounding prototype NLP analysis of the demographic survey. 

### Usage

In order to create any model, the user must have secure access to the required underlying datasets - these are IDIR restricted. To gain access to the database, a `credentials.txt` file must exist in the top level of this repository of the form: 

```
DRIVER=DRIVER_TYPE;
SERVER=SERVER_NAME;
DATABASE=DATABASE_NAME;
Trusted_Connection=yes;
```

A sample connections file can be provided if necessary, after a review of the reasons for requiring access.

* All source code is stored in the `src` folder
* New models can be produced or new results appended via notebooks in the `notebooks` folder.
* There are two types of models:

    * Q32 and Q22 both utilize full data cleaning, transformation and random forest models to predict likely and tentative categories.
    * To create a new model, run `create_model_qXX.ipynb`. 
    * To append new model results to the question, run `predict_model_qXX.ipynb`.
    * Q29, Q30, and Q34 are a simpler exact and partial match model that utilize data cleaning and comparisons against category words to identify whether a response is an exact or partial match to a category.
    * To produce new results, run `q**_cleaning.ipynb`.
    * Additional notebooks to compare final results of manual coding to the automated coding have further been created in `reporting_metrics_qXX.ipynb`. These pull in the final data after all coding methods have been completed, and compare to the model outputs. 

### Getting Help or Reporting an Issue

To report bugs/issues/feature requests, please file an [issue](https://github.com/bcgov/demo-nlp/issues/).


### How to Contribute

If you would like to contribute, please see our [CONTRIBUTING](CONTRIBUTING.md) guidelines.

Please note that this project is released with a [Contributor Code of Conduct](CODE_OF_CONDUCT.md). By participating in this project you agree to abide by its terms.

### License

```
Copyright 2023 Province of British Columbia

Licensed under the Apache License, Version 2.0 (the &quot;License&quot;);
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an &quot;AS IS&quot; BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and limitations under the License.
```
---
