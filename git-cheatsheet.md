# Working with Git Repos
---

### Initial Local Repository Setup (Done Once)
---

1. Using git bash, navigate to the location you wish to create your repo. This can be done using: 

   `cd path\to\folder\`

2. Set up a new local repository from something exisiting on GitHub:

   `git clone <URL>`

   The URL is copied from the GitHub repo you are wishing to create.


### General Pull Request Workflow (repeat 4-6 as needed)
---

3. Create a new branch. You will typically always want to do this, try to never work directly on the `main` branch.

   `git checkout -b <branchname>`

4. Make your changes as needed to the code. 

5. Commit all changes to branch:

   `git add <filenames>`

   `git commit -m "Descriptive comment of what I changed/updated"`

6. Push branch with changes back to the remote (origin):

   `git push -u origin <branchname>`

   or for subsequent changes to the pull request, setting up the origin to track this branch is not neccessary:

   `git push`

7. On GitHub:

   Click `Compare & Pull Request`

   Request a reviewer (someone else on the team)

   Reviewer: request changes or approve

   Once approved: Original author merges into the `main` branch and deletes the extra branch.

### Tidying Up An Approved Pull Request
--- 

8. Get local repo back up-to-date on the `main` branch:

   `git checkout main`

   `git pull`

9. Delete the old local branch you were working on:

   `git branch -d <branchname>`