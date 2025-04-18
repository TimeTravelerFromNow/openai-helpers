import os
import re
import sys
import logging
from os.path import join, dirname, exists
from typing import Dict, Any, List, Union, Optional, Tuple

# Helper function to escape special regex characters
def escape_regexp(string: str) -> str:
    """Escape special regex characters in a string."""
    return re.escape(string)

def str_replace_editor(tool_call: Dict[str, Any]) -> Dict[str, Any]:
    if not exists('./tmp/assistant-changes'):
        raise Exception('This tool is hardcoded to make changes in the ./tmp/assistant-changes directory. ensure it is created and handle by your code.')
    """
    Handle file operations like viewing, replacing text, and inserting content.

    Args:
        tool_call: Dictionary containing the tool call information

    Returns:
        Dict with the response format for the user
    """
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
                dir_path = join(dirname(__file__), './tmp/assistant-changes', file_path)
                if not exists(dir_path):
                    result = f"Directory '{file_path}' does not exist. Please check the path and try again."
                    is_error = True
                else:
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
                safe_path = file_path.replace('..', '')
                full_path = join(dirname(__file__), './tmp/assistant-changes', safe_path)

                if not exists(full_path):
                    result = "Error: File not found"
                    is_error = True
                else:
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
                    safe_path = replace_path.replace('..', '')
                    full_path = join(dirname(__file__), './tmp/assistant-changes', safe_path)

                    if not exists(full_path):
                        result = "Error: File not found"
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
                    safe_path = insert_path.replace('..', '')
                    full_path = join(dirname(__file__), './tmp/assistant-changes', safe_path)

                    if not exists(full_path):
                        result = "Error: File not found"
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

        elif command == 'undo_edit':
            # Handle undoing edits
            result = "undo_edit not yet implemented"
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
