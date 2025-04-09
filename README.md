# openai-helpers

### Setup

## Dependencies

Using pyenv

`pyenv install 3.12`
`pyenv local 3.12`
`pip install dotenv openai`

### Credentials

In your project directory, you should have a `.env` file set up to use your openai api key

```
# your .env file
OPENAI_API_KEY='your-open-ai-account-api-key'
```

### Usage

- clone this repository into your project directory
- cd back into your project directory
- initialize the OpenAI client
- At the beginning of your scripts, load the .env file
- import this helper module

```
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()
client = OpenAI()

from openai_helpers import *`
```

#### How to call a function

Helpful to show an example usage:

`get_processed_run(run, thread_id)`

This function will poll the run status until its status is out of `queued`, and then return the refreshed run.

`completed_run = get_processed_run(run, thread_id)`

OpenAI api one-liners dont need to be in this helper module, but feel free to add additional functions into the `openai_helpers` module to tidy up your code workspace. 

### Contributing

Fork the repo, open a PR with instructions how to use your new function and why it makes sense as a helper function 
