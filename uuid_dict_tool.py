import uuid
import json
import argparse
import re
import shutil
from pathlib import Path


# Constants

FILE_TYPES = ["lsx", "txt", "xml"]


# Parse program arguments

parser = argparse.ArgumentParser(description="BG3 Modding UUID Tool",
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument("-d", "--dict", default="uuid_dict.json",
                    help="UUID dictionary filepath.")
parser.add_argument("-p", "--prefix", default="lhandle_",
                    help="The prefix that identifies your localization handles.")
parser.add_argument("-o", "--overwrite", action="store_true",
                    help="Overwrite the files in your mod directory,"
                    " rather than creating new ones. Use with caution.") 
parser.add_argument("src", help="Path to the working directory of your mod")
parser.add_argument("-t", "--target", default="UUID_tool_output",
                    help="Path or name of the target directory."
                    " When given a relative path, it will be rooted"
                    " in the same directory as the src directory.")
parser.add_argument("-v", "--verbose", action="store_true",
                    help="Increase verbosity")
args = vars(parser.parse_args())

uuid_dict_path: Path = Path(args["dict"])
prefix: str = args["prefix"]
overwrite: bool = args["overwrite"]
src_path: Path = Path(args["src"])
dst_path: Path
if overwrite:
  dst_path = src_path
else:
  dst_path = Path(args["target"])
  if not dst_path.is_absolute():
    dst_path = src_path.parent / dst_path
verbose: bool = args["verbose"]


# Handle path arguments

# Set verbosity
verboseprint = print if verbose else lambda *a, **k: None

# Load dictionary
uuid_dict: dict
if uuid_dict_path.exists():
  with uuid_dict_path.open('r') as uuid_dict_file:
    verboseprint("loading dictionary...")
    uuid_dict = json.load(uuid_dict_file)
else:
  verboseprint("no existing dictionary")
  uuid_dict = {}

# Copy directories and files to target directory
if not overwrite:
  verboseprint("copying mod directory...")
  shutil.copytree(src_path, dst_path, dirs_exist_ok=True)

# Compile list of files to scan
verboseprint("compiling file list...")
file_paths = []
for file_type in FILE_TYPES:
  file_paths.extend(list(src_path.rglob(f"*.{file_type}")))


# Compile regular expressions

uuid_pattern = re.compile(r"[0-9A-Fa-f]{8}-"
                          r"([0-9A-Fa-f]{4}-){3}"
                          r"[0-9A-Fa-f]{12}"
                          )
guid_location_pattern = re.compile(
  # Locate /<attribute/
  r"<attribute"

  # Locate /type = "guid"/
  r".*?(?P<type>type\s*?=\s*?" "[\"\']guid[\"\']" r")?"

  # Locate /value = "YOUR_PLACEHOLDER"/
  r".*?value\s*?=\s*?"
  "[\"\']" r"(?P<placeholder>.+?)" "[\"\']"

  # Locate /type = "guid".../>/ if not located already, otherwise //>/
  r".*?(?(type)/>|type\s*?=\s*?" "[\"\']guid[\"\']" r".*?/>)"
  )
selector_location_pattern = re.compile(r"(Select|Add).*?"
                                       r"\((?P<placeholder>.+?)[,\)]"
                                       )
handle_location_pattern = re.compile("[\"\']" 
                                     r"(?P<placeholder>\s*" + prefix + r".+?)"
                                     r"(;\s*\d*\s*)?"
                                     "[\"\']"
                                     )


# Define helper functions

def uuid_str_to_handle(uuid_str: str) -> str:
  # Returns a localization handle string converted from a UUID string
  return 'h' + uuid_str.replace('-', 'g')

def new_uuid() -> str:
  return str(uuid.uuid4())

def new_handle() -> str:
  return uuid_str_to_handle(new_uuid())

def new_entry(handle: bool) -> str:
  # Returns a new UUID, or a new localization handle if handle=True
  return new_handle() if handle else new_uuid()


def replace_all(pattern: re.Pattern[str], content: str, handle=False) -> str:
  # Return a string where all placeholders identified by pattern in 
  # content are replaced with an ID (UUID, or localization handle if 
  # handle=True). 
  # IDs are dictated by the placeholder names in uuid_dict. 
  # If no entry exists for a placeholder, a new ID is generated first 
  # and added to uuid_dict, before replacing the placeholder in content.
  global uuid_dict
  for mtch in re.finditer(pattern, content):
    name = mtch["placeholder"]
    if handle or not uuid_pattern.fullmatch(name):
      if name and name not in uuid_dict:
        uuid_dict[name] = new_entry(handle)
      content = re.sub("(?<=[\"\'\\(])" + name + "(?=[\"\'\\),;])", uuid_dict[name], content)
  return content


## Replace UUID and localization handle placeholders with UUIDs and localization handles
content = ""
print("replacing UUID and handle placeholders...")
for path in file_paths:
  content = path.read_text()
  content = replace_all(guid_location_pattern, content)
  content = replace_all(selector_location_pattern, content)
  content = replace_all(handle_location_pattern, content, handle=True)
  
  if overwrite:
    dst_sub_path = path
  else:
    sub_path = path.relative_to(src_path)
    dst_sub_path = dst_path / sub_path
  
  dst_sub_path.write_text(content)
  verboseprint(str(path.relative_to(src_path)) + ": done")

## Save dictionary to file
verboseprint("storing dictionary...")
with uuid_dict_path.open('w') as uuid_dict_file:
  json.dump(uuid_dict, uuid_dict_file, indent=2, sort_keys=True)

print("...done!")