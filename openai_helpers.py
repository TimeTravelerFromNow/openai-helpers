# openai_helpers.py
###########
# the purpose of the openai helpers is to abstract away some processing logic into helpers for the openai API
# Things that are one liners, dont require additional handling logic, you should call regularly within your script as client.beta...
#######
from openai import OpenAI
import time
import json

client = OpenAI()

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
    MAX_ITER=100 # 30 seconds max
    SLEEP=0.3
    i = 0
    is_incomplete_status = (run.status == 'queued' or run.status == 'in_progress')
    while is_incomplete_status and i < MAX_ITER:
        is_incomplete_status = (run.status == 'queued' or run.status == 'in_progress')
        run = client.beta.threads.runs.retrieve(
            thread_id=thread_id,
            run_id=run.id
        )
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
            print("assistant_iteration: {}".format(assistant_iteration))
    match run.status:
        case 'completed':
            return 'prompt_user'
        case 'requires_action':
            # check required action type is to submit tool outputs
            if run.required_action.type == 'submit_tool_outputs':
                required_action = run.required_action.submit_tool_outputs
                tool_call = required_action.tool_calls[0]
                function_name = tool_call.function.name
                arguments = tool_call.function.arguments
                if tool_call.type == 'function':
                    # function call
                    print("Assistant is calling the {} function \n with arguments: {}".format(function_name, arguments))
                    json_args = json.loads(arguments)
                    tool_output = _func_caller(function_name, json_args)
                    run = client.beta.threads.runs.submit_tool_outputs(
                        thread_id=thread_id,
                        run_id=run.id,
                        tool_outputs=[
                            {
                                "tool_call_id":tool_call.id,
                                "output": tool_output
                            }
                        ]
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

### Destructors
def remove_from_file_store(file_paths):
    print('implement me CLEANUP remove_from_file_store!!')

def delete_thread(thread_id=''):
    result = client.beta.threads.delete(thread_id)
    if result.deleted:
        print('successfully deleted thread')
    else:
        print("thread not successfully deleted")
