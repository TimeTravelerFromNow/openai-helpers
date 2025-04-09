# openai-helpers

### Setup

## Dependencies

Using pyenv

`pyenv install 3.12`
`pyenv local 3.12`
`pip install dotenv openai`

### Credentials
`cp dotenv-example .env`  in the same directory as your project 
edit .env to use your openai api key

```
# your .env file
OPENAI_API_KEY='your-open-ai-account-api-key'
```

Make sure to load the .env file using `dotenv` in your project

### Usage

At the beginning of your scripts, import all the functions
`from openai_helpers import *`
`from dotenv import load_dotenv`

Load the .env file, and make the global `client` variable.
`load_dotenv()`
`client = OpenAI()`


#### How to call a function
For example, the `get_processed_run(run, thread_id)`
function will poll the run status until its status is out of `queued`, and then return the refreshed run.

`completed_run = get_processed_run(run, thread_id)`

OpenAI api one-liners dont need to be in this helper module, but feel free to add additional functions into the `openai_helpers` module to tidy up your code workspace. 

### Contributing

Fork the repo, open a PR with instructions how to use your new function and why it makes sense as a helper function 
