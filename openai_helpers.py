# openai_helpers.py
###########
# the purpose of the openai helpers is to abstract away some processing logic into helpers for the openai API
# Things that are one liners, dont require additional handling logic, you should call regularly within your script as client.beta...
#######
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI()
FILE_STORE = client.vector_stores.create(name="Style and HTML Files")

# Retrieve an openai assistant by ID
def retrieve_assistant_by_id(assistant_id):
    try:
        assistant = client.beta.assistants.retrieve(assistant_id)
        return assistant
    except Exception as e:
        print(f"Error retrieving assistant: {e}")
        return None

def upload_to_file_store(file_paths):
    # Ready the files for upload to OpenAI
    file_streams = [open(path, "rb") for path in file_paths]
    
    # Use the upload and poll SDK helper to upload the files, add them to the vector store,
    # and poll the status of the file batch for completion.
    file_batch = client.vector_stores.file_batches.upload_and_poll(
      vector_store_id=file_store.id, files=file_streams
    )

def remove_from_file_store(file_paths):
    #cleanup code
    print('implement me CLEANUP remove_from_file_store!!')

def get_processed_run(run, thread_id):
    MAX_ITER=100 # 30 seconds max
    SLEEP=0.3
    run = client.beta.threads.runs.retrieve(
        thread_id=thread_id,
        run_id=run.id
    )
    while run.status == 'queued' and i < MAX_ITER:
        time.sleep(SLEEP)
        i += 1
    if run.status == 'queued':
        raise Exception('Assistant stuck in queued: TIMEOUT after {} seconds'.format(SLEEP*MAX_ITER))
    else:
        return run

def delete_thread(thread_id=''):
    result = client.beta.threads.delete(thread_id)
    if result.deleted:
        print('successfully deleted thread')
    else:
        print("thread not successfully deleted")
