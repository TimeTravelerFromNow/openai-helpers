# openai_helpers.py
###########
# the purpose of the openai helpers is to abstract away some processing logic into helpers for the openai API
# Things that are one liners, dont require additional handling logic, you should call regularly within your script as client.beta...
#######
from openai import OpenAI
import time
import json
import os
import shutil

client = OpenAI()
FILE_IDS = []

# Retrieve an openai assistant by ID
def retrieve_assistant_by_id(assistant_id):
    try:
        assistant = client.beta.assistants.retrieve(assistant_id)
        return assistant
    except Exception as e:
        print(f"Error retrieving assistant: {e}")
        return None

# Create a directory for extension overrides if it doesn't exist
TMP_EXT_OVERRIDES_DIR = os.path.join("tmp", "ext-overrides")
os.makedirs(TMP_EXT_OVERRIDES_DIR, exist_ok=True)

def get_compatible_file_stream(file_path):
    """
    Creates a compatible file stream for the vector store.
    If the file has an unsupported extension, it's copied to a tmp directory with a compatible extension.
    Args:
        file_path: Path to the original file
    Returns:
        file_stream
    """
    # Get the base name and extension
    base_name = os.path.basename(file_path)
    name, ext = os.path.splitext(base_name)

    # override unsupported file extensions
    new_ext = ext
    if ext == '.scss':
        new_ext = '.css'
    elif ext == '.html.liquid':
        new_ext = '.html'
    elif ext == '.png':
        raise Exception("PNG files are not supported for vector store")

    # If the extension is already compatible, just open the original file
    if new_ext == ext:
        file_stream = open(file_path, "rb")
        return file_stream

    # Create a new file in the tmp directory with the compatible extension
    new_filename = name + new_ext
    new_path = os.path.join(TMP_EXT_OVERRIDES_DIR, new_filename)

    # Copy the content from the original file to the new file
    shutil.copy2(file_path, new_path)
    # Open the new file for the vector store
    file_stream = open(new_path, "rb")

    return file_stream

def upload_and_add_to_vector_store(file_paths=[],vector_store_id=""):
    (file_ids,missing_file_names) = upload_files_to_openai(file_paths)
    print(f"uploaded files to openai: {file_ids}")

    if len(file_ids)==0:
        return (file_ids,missing_file_names)

    vector_store_file_batch = client.vector_stores.file_batches.create(
        vector_store_id=vector_store_id,
        file_ids=file_ids
    )
    print(f"uploading {file_paths} to vector store, batch {vector_store_file_batch.id}")
    i = 0
    while vector_store_file_batch.status != "completed" and i <= MAX_ITER:
        vector_store_file_batch = client.vector_stores.file_batches.retrieve(
            vector_store_id=vector_store_id,
            batch_id=vector_store_file_batch.id
        )
        time.sleep(0.3)
        print(".",end="")
        i += 1
    print(f"done with vector store file batch ids: {file_ids}")
    # No need for global declaration here since we're just reading
    FILE_IDS.extend(file_ids)
    return (file_ids,missing_file_names)

def upload_files_to_openai(file_paths):
    """
    Uploads files to OpenAI, returns an array of file ids
    """
    # Ready the files for upload to OpenAI
    file_streams = []
    file_ids = []
    missing_file_names = []
    for path in file_paths:
        # Get a compatible file stream
        try:
            file_stream = get_compatible_file_stream(path)
            file_streams.append(file_stream)
        except Exception as e:
            missing_file_names.append(path)
            continue

        try:
            response = client.files.create(
                file=file_stream,
                purpose="assistants"
            )
            file_ids.append(response.id)
            file_stream.close()
        except Exception as e:
            file_stream.close()
            print(f"Error uploading file: {e}")

    return (file_ids,missing_file_names)

def create_vector_store_file(file_id="",vector_store_id=""):
    """
    Add a file to the vector store
    """
    response = client.vector_stores.files.create(
        vector_store_id=vector_store_id,
        file_id=file_id
    )
    return response

# get_latest_message(thread_id)
# returns content of string of latest message posted to the thread.
def get_latest_message(thread_id):
    thread_messages = client.beta.threads.messages.list(thread_id)
    latest_message = thread_messages.data[0]
    content = latest_message.content
    for content in latest_message.content:
        if content.type == "text":
            return content.text.value
        else:
            print("Dont know how to get latest message type {}".format(content.type))
            return ""

def print_message_history(thread_id):
    messages = client.beta.threads.messages.list(thread_id)
    for m in messages.data:
        for content in m.content:
            match content.type:
                case "text":
                    print(content.text.value)
                case _:
                    print("Not yet implemented for handling content type {}".format(content.type))


def get_processed_run(run, thread_id):
    if run.status == "expired":
        raise Exception("Assistant run expired {}".format(run))
    MAX_ITER=100 # 30 seconds max
    SLEEP=0.3
    i = 0
    is_incomplete_status = (run.status == 'queued' or run.status == 'in_progress')
    print("polling run {} ".format(run.id),end="")
    while is_incomplete_status and i < MAX_ITER:
        run = client.beta.threads.runs.retrieve(
            thread_id=thread_id,
            run_id=run.id
        )
        is_incomplete_status = (run.status == 'queued' or run.status == 'in_progress')
        print(".",end="")
        time.sleep(SLEEP)
        i += 1
    if is_incomplete_status:
        raise Exception('Assistant stuck with {} status: TIMEOUT after {} seconds'.format(run.status,SLEEP*MAX_ITER))
    else:
        return run

### handle_run_result Handles the run result to determine next steps
# Parameters:
# run: the run object to handle
# thread_id: thread id of the run
# _func_caller: function(function_name, arguments) # calls and returns custom code.
# Define once and implement your call_custom_function somewhere in your script.
# Returns string:
# 'prompt_user' if the run is completed
# 'continue_assistant' if the run is requires_action
# else raise exception
###
MAX_ITER = 20
assistant_iteration = 0
def handle_run_result(run=None,thread_id='',_func_caller=None,is_recursing=False):
    global assistant_iteration

    run = get_processed_run(run, thread_id)
    if not is_recursing:
        assistant_iteration = 0 # reset the safety counter
    else:
        if assistant_iteration >= MAX_ITER:
            raise Exception("MAX_ITER safety limit hit for assistant runs")
        else:
            assistant_iteration += 1
            print("\nassistant_iteration: {}".format(assistant_iteration))
    match run.status:
        case 'completed':
            return 'prompt_user'
        case 'requires_action':
            # check required action type is to submit tool outputs
            if run.required_action.type == 'submit_tool_outputs':
                required_action = run.required_action.submit_tool_outputs
                run =serve_tool_calls(
                    tool_calls=required_action.tool_calls,
                    run_id=run.id,
                    thread_id=thread_id,
                    _func_caller=_func_caller
                )

                return handle_run_result(
                    run=run,
                    thread_id=thread_id,
                    _func_caller=_func_caller,
                    is_recursing=True
                )
        case 'cancelled':
            raise Exception('Assistant run cancelled')
        case _:
            raise Exception('Unknown assistant run status {}'.format(run.status))

# serve_tool_calls
# tool_calls: list of tool calls
# _func_caller: function(function_name, arguments) # calls and returns custom code.
# Define once and implement your call_custom_function somewhere in your script.
# Returns run object after submitting tool outputs.
def serve_tool_calls(tool_calls=None, run_id="", thread_id="", _func_caller=None):
    function_outputs = [{
        "tool_call_id": tool_call.id,
        "output": _func_caller(tool_call.function.name, json.loads(tool_call.function.arguments))
    } for tool_call in tool_calls]

    run = client.beta.threads.runs.submit_tool_outputs(
                thread_id=thread_id,
                run_id=run_id,
                tool_outputs=function_outputs
            )
    return run

### Destructors
def delete_files_from_openai(file_ids=[],vector_store_id=None):
    for file_id in file_ids:
        (vs_result, del_result) = delete_openai_file(
            file_id=file_id,
            vector_store_id=vector_store_id
        )
        if vs_result:
            print(f"{vs_result}")
        if del_result:
            print(f"{del_result}")

        FILE_IDS.remove(file_id)

def remove_files_from_vector_store(file_ids=[],vector_store_id=""):
    result=""
    for file_id in file_ids:
        if not file_id.startswith('file-'):
            file_id = 'file-' + file_id
        try :
            result = client.vector_stores.files.delete(
                vector_store_id=vector_store_id,
                file_id=file_id
            )
            print(f"{result}")
        except:
            print(f"Error deleting file {file_id} from vector store {vector_store_id}")
            continue
    return result.object

def delete_openai_file(file_id="",vector_store_id=None):
    """
    Delete a file from the vector store if given a vector store id and delete from openai file storage
    Dont really care about local tmp for the time being
    Returns a tuple of (response,response) for the vector store and file storage deletion calls respectively
    """
    (vector_store_response,deletion_handler_response) = (None,None)
    if vector_store_id:
        vector_store_response = client.vector_stores.files.delete(
            vector_store_id=vector_store_id,
            file_id=file_id
        )
    deletion_handler_response = client.files.delete(file_id)
    FILE_IDS.remove(file_id)
    return (vector_store_response,deletion_handler_response)

def delete_thread(thread_id=''):
    result = client.beta.threads.delete(thread_id)
    if result.deleted:
        print('successfully deleted thread')
    else:
        print("thread not successfully deleted")

def clear_openai_storage(vector_store_id=None):
    print(f"Starting to cleanup of all files {len(FILE_IDS)} from OpenAI, thanks for being tidy!".format(FILE_IDS))
    # No need for global declaration here since we're modifying through functions
    for file_id in FILE_IDS[:]:  # Create a copy of the list to iterate over
        (vector_store_response,deletion_handler_response) = delete_openai_file(file_id,vector_store_id)
        if vector_store_response:
            print(f"{vector_store_response}")
        if deletion_handler_response:
            print(f"{deletion_handler_response}")
    print("Done deleting, files should be gone: FILE_IDS={}".format(FILE_IDS))
    if vector_store_id:
        print("deleting the vector store too")
        result = client.vector_stores.delete(vector_store_id)
        print(f"Done deleting, vector store should be gone\n{result}")
