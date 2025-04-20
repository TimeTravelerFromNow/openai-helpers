# openai_helpers.py
###########
# the purpose of the openai helpers is to abstract away some processing logic into helpers for the openai API
# Things that are one liners, dont require additional handling logic, you should call regularly within your script as client.beta...
#######

# Standard library imports
import os
import re
import time
import json
import logging
import shutil
from os.path import join, dirname, exists
from typing import Dict, Any, List, Union, Optional, Tuple
from pathlib import Path

# Third-party imports
from openai import OpenAI

# Initialize OpenAI client
client = OpenAI()
FILE_IDS = [] # keep track for deletion

### STR_REPLACE_EDITOR

# Helper function to escape special regex characters
def escape_regexp(string: str) -> str:
    """Escape special regex characters in a string."""
    return re.escape(string)

def handle_function_call(function_name: str, arguments: Dict[str, Any]) -> str:
    """
    Handle function calls in OpenAI format.

    Args:
        function_name: The name of the function to call
        arguments: Dictionary of arguments for the function

    Returns:
        Result as a string
    """
    if function_name == "str_replace_editor":
        # For str_replace_editor calls, create the tool_call object
        tool_call = {
            "name": "str_replace_editor",
            "input": arguments
        }
        result = str_replace_editor(tool_call)
        return json.dumps(result)
    else:
        return json.dumps({
            "content": f"Unknown function: {function_name}",
            "is_error": True
        })

def str_replace_editor(tool_call: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle file operations like viewing, replacing text, and inserting content.

    Args:
        tool_call: Dictionary containing the tool call information

    Returns:
        Dict with the response format for the user
    """
    # Define assistant-changes directory - the only root we should use
    assistant_changes_dir = 'tmp/assistant-changes'

    if not exists(assistant_changes_dir):
        raise Exception(f'This tool is hardcoded to make changes in the {assistant_changes_dir} directory. ensure it is created and handle by your code.')

    # Validate tool call structure
    if not tool_call or not tool_call.get('name') or not tool_call.get('input'):
        logging.error(f'Invalid tool call: {tool_call}')
        return {
            "content": "Invalid tool call structure",
            "is_error": True
        }

    input_params = tool_call.get('input', {})
    command = input_params.get('command', 'view')
    file_path = input_params.get('path', '/')
    result = None
    is_error = False

    try:
        # Process based on tool name first
        if tool_call.get('name') != 'str_replace_editor':
            return {
                "content": f"Unknown tool: {tool_call.get('name')}",
                "is_error": True
            }

        # Process based on command
        if command == 'view':
            # Handle viewing files and directories
            if file_path == '/' or file_path.endswith('/'):
                # Clean path to prevent directory traversal
                safe_path = file_path.replace('..', '')
                dir_path = join(assistant_changes_dir, safe_path)
                print(f"Looking for directory at: {dir_path}")

                if not exists(dir_path):
                    result = f"Directory '{file_path}' does not exist. Please check the path and try again."
                    is_error = True
                else:
                    # Found the directory
                    items = os.listdir(dir_path)
                    contents = []

                    for index, item_name in enumerate(items):
                        item_path = join(dir_path, item_name)
                        if os.path.isdir(item_path):
                            contents.append(f"{index + 1}: {item_name}/")
                        elif re.search(r'\.(html|html\.liquid|scss|css|js|json)$', item_name):
                            contents.append(f"{index + 1}: {item_name}")

                    result = '\n'.join(contents)
            else:
                # Try file path
                safe_path = file_path.replace('..', '')
                full_path = join(assistant_changes_dir, safe_path)
                print(f"Trying file path: {full_path}")

                if not exists(full_path):
                    result = f"Error: File not found at {file_path}"
                    is_error = True
                elif os.path.isdir(full_path):
                    # Special case for trying to view a directory as a file
                    result = f"Error: This is a directory, not a file. Use a trailing slash to view directory contents."
                    is_error = True
                else:
                    try:
                        with open(full_path, 'r', encoding='utf-8') as f:
                            content = f.read()

                        lines = content.split('\n')

                        if input_params.get('view_range'):
                            start, end = input_params['view_range']
                            if end == -1:
                                selected_lines = lines[start-1:]
                            else:
                                selected_lines = lines[start-1:end]
                            result = '\n'.join([f"{start + i}: {line}" for i, line in enumerate(selected_lines)])
                        else:
                            result = '\n'.join([f"{index + 1}: {line}" for index, line in enumerate(lines)])
                    except Exception as read_error:
                        result = f"Error reading file: {str(read_error)}"
                        is_error = True

        elif command == 'str_replace':
            # Handle text replacement in files
            try:
                replace_path = input_params.get('path')
                original_text = input_params.get('old_str')
                replacement_text = input_params.get('new_str')
                match_count = input_params.get('match_count')

                if not replace_path or not original_text or replacement_text is None:
                    result = "Error: Missing required parameters for str_replace"
                    is_error = True
                else:
                    # Clean path to prevent directory traversal
                    safe_path = replace_path.replace('..', '')
                    full_path = join(assistant_changes_dir, safe_path)
                    print(f"Trying file path: {full_path}")

                    if not exists(full_path):
                        result = f"Error: File not found at {replace_path}"
                        is_error = True
                    else:
                        with open(full_path, 'r', encoding='utf-8') as f:
                            file_content = f.read()

                        # Count matches
                        escaped_text = escape_regexp(original_text)
                        matches = re.findall(escaped_text, file_content)
                        num_matches = len(matches)

                        # Handle no matches
                        if num_matches == 0:
                            result = "Error: No match found for replacement. Please check your text and try again."
                            is_error = True
                        # Handle multiple matches
                        elif num_matches > 1 and not match_count:
                            result = f"Error: Found {num_matches} matches for replacement text. Please provide more context to make a unique match."
                            is_error = True
                        else:
                            # Perform the replacement
                            try:
                                new_content = re.sub(escaped_text, replacement_text, file_content)
                                with open(full_path, 'w', encoding='utf-8') as f:
                                    f.write(new_content)

                                location_text = "exactly one location" if num_matches == 1 else f"{num_matches} locations"
                                result = f"Successfully replaced text at {location_text}."
                            except Exception as write_error:
                                if "permission" in str(write_error).lower():
                                    result = "Error: Permission denied. Cannot write to file."
                                else:
                                    result = f"Error performing file write: {str(write_error)}"
                                is_error = True
            except Exception as error:
                error_message = f"Error performing str_replace: {str(error)}"

                if "permission" in str(error).lower():
                    error_message = "Error: Permission denied. Cannot write to file."

                result = error_message
                is_error = True

        elif command == 'create':
            # Handle file creation
            result = "create not yet implemented"
            is_error = True

        elif command == 'insert':
            # Handle text insertion
            try:
                insert_path = input_params.get('path')
                insert_line = input_params.get('insert_line', 0)
                if not isinstance(insert_line, int):
                    insert_line = 0
                new_text = input_params.get('new_str')

                if not insert_path or new_text is None:
                    result = "Error: Missing required parameters for insert"
                    is_error = True
                else:
                    # Clean path to prevent directory traversal
                    safe_path = insert_path.replace('..', '')
                    full_path = join(assistant_changes_dir, safe_path)
                    print(f"Trying file path: {full_path}")

                    if not exists(full_path):
                        result = f"Error: File not found at {insert_path}"
                        is_error = True
                    else:
                        # Read the file
                        try:
                            with open(full_path, 'r', encoding='utf-8') as f:
                                file_content = f.read()

                            lines = file_content.split('\n')

                            # Verify insert_line is within bounds
                            if insert_line < 0 or insert_line > len(lines):
                                result = f"Error: Line number {insert_line} is out of bounds (file has {len(lines)} lines)"
                                is_error = True
                            else:
                                # Insert the new text at the specified position
                                new_text_lines = new_text.split('\n')
                                for i, line in enumerate(new_text_lines):
                                    lines.insert(insert_line + i, line)

                                # Write the file back
                                try:
                                    with open(full_path, 'w', encoding='utf-8') as f:
                                        f.write('\n'.join(lines))

                                    plural = 's' if len(new_text_lines) != 1 else ''
                                    result = f"Successfully inserted {len(new_text_lines)} line{plural} at position {insert_line}."
                                except Exception as write_error:
                                    if "permission" in str(write_error).lower():
                                        result = "Error: Permission denied. Cannot write to file."
                                    else:
                                        result = f"Error performing file write: {str(write_error)}"
                                    is_error = True
                        except Exception as read_error:
                            if "permission" in str(read_error).lower():
                                result = "Error: Permission denied. Cannot read file."
                            else:
                                result = f"Error reading file: {str(read_error)}"
                            is_error = True
            except Exception as error:
                error_message = f"Error performing insert: {str(error)}"

                if "permission" in str(error).lower():
                    error_message = "Error: Permission denied. Cannot access file."

                result = error_message
                is_error = True

        elif command == 'delete':
            # Handle file deletion
            try:
                delete_path = input_params.get('path')

                if not delete_path:
                    result = "Error: Missing required path parameter for delete"
                    is_error = True
                else:
                    # Clean path to prevent directory traversal
                    safe_path = delete_path.replace('..', '')
                    full_path = join(assistant_changes_dir, safe_path)
                    print(f"Trying file path: {full_path}")

                    if not exists(full_path):
                        result = f"Error: File not found at {delete_path}"
                        is_error = True
                    else:
                        try:
                            if os.path.isdir(full_path):
                                import shutil
                                shutil.rmtree(full_path)
                                result = f"Successfully deleted directory: {delete_path}"
                            else:
                                os.remove(full_path)
                                result = f"Successfully deleted file: {delete_path}"
                        except PermissionError:
                            result = f"Error: Permission denied. Cannot delete {delete_path}"
                            is_error = True
                        except IsADirectoryError:
                            result = f"Error: {delete_path} is a directory. Use delete with a directory flag."
                            is_error = True
                        except Exception as delete_error:
                            result = f"Error deleting {delete_path}: {str(delete_error)}"
                            is_error = True
            except Exception as error:
                error_message = f"Error performing delete operation: {str(error)}"
                if "permission" in str(error).lower():
                    error_message = "Error: Permission denied. Cannot delete file."
                result = error_message
                is_error = True

        else:
            result = f"Unknown command: {command}"
            is_error = True

        # Return formatted response
        return {
            "content": result,
            "is_error": is_error
        }

    except Exception as error:
        logging.error(f"Error handling {command} command: {error}")

        error_message = f"Failed to execute {command}: {str(error)}"

        # Check for permission errors
        if "permission" in str(error).lower():
            error_message = "Error: Permission denied. Cannot access file."

        return {
            "content": error_message,
            "is_error": True
        }




### OPENAI HELPERS
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
    usage_data = process_run_usage(run)
    log_token_usage(usage_data)
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
    function_outputs = []

    for tool_call in tool_calls:
        function_name = tool_call.function.name
        arguments = json.loads(tool_call.function.arguments)

        # Check if the function is str_replace_editor
        if function_name == "str_replace_editor":
            # Use the directly integrated handle_function_call function
            print("editor args: {}".format(arguments))
            output = handle_function_call(function_name, arguments)
        else:
            # Use the provided function caller for other functions
            output = _func_caller(function_name, arguments)

        function_outputs.append({
            "tool_call_id": tool_call.id,
            "output": output
        })
    print("tool_outputs: {}".format(str(function_outputs)[:500]))

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

def clear_assistant_tmp():
    tmp_dir = Path("tmp/assistant-changes")
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
        print("Temporary directory 'tmp/assistant-changes' has been cleared.")
    else:
        print("Temporary directory 'tmp/assistant-changes' does not exist.")

def process_run_usage(run):
    """
    Extracts and processes token usage data from a completed run.
    Returns a dictionary with usage metrics.
    """
    if not hasattr(run, 'usage') or run.usage is None:
        return None

    usage_data = {
        'run_id': run.id,
        'thread_id': run.thread_id,
        'assistant_id': run.assistant_id,
        'model': run.model,
        'timestamp': run.completed_at,
        'prompt_tokens': run.usage.prompt_tokens,
        'completion_tokens': run.usage.completion_tokens,
        'total_tokens': run.usage.total_tokens
    }

    return usage_data

def log_token_usage(usage_data, base_dir="tmp/logs"):
    """
    Logs token usage data to a CSV file with format usage_{thread_id}.csv
    Creates the directory if it doesn't exist.
    """
    if not usage_data:
        return None

    import csv
    import os

    # Create logs directory if it doesn't exist
    os.makedirs(base_dir, exist_ok=True)

    # Generate filename based only on thread_id
    thread_id = usage_data.get('thread_id', 'unknown_thread')
    filename = f"usage_{thread_id}.csv"
    filepath = os.path.join(base_dir, filename)

    # Check if file exists to determine if headers are needed
    file_exists = os.path.isfile(filepath)

    with open(filepath, 'a', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=usage_data.keys())
        if not file_exists:
            writer.writeheader()
        writer.writerow(usage_data)

    return filepath
