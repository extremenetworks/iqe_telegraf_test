import json
import os
import ipaddress
import common as common_m
import yaml

# AP and server creds
apIp = '10.234.51.31'
user = 'admin'
pwd = 'Admin@123'
api_host_name = '10.234.165.202'
port_number = 9000

def get_ref_from_spec(spec, ref):
    expected_prefix = "#/components/schemas/"
    if not ref.startswith(expected_prefix):
        return None
    ref = ref[len(expected_prefix):]
    split_ref = ref.split("/")
    for element in split_ref:
        spec = spec.get(element, None)
        if spec is None:
            return None
    return spec

def validate_object_spec(spec, obj, obj_name, schemas_spec):
    if obj is None:
        if spec.get("nullable", False):
            return None
        else:
            return f"{obj_name} cannot be null"

    if "$ref" in spec:
        p_spec = get_ref_from_spec(schemas_spec, spec["$ref"])
        if p_spec is None:
            return f"Could not follow schema reference {spec['$ref']} while validating {obj_name}"
        return validate_object_spec(p_spec, obj, obj_name, schemas_spec)

    if "allOf" in spec:
        for all_spec in spec.get("allOf", []):
            result = validate_object_spec(all_spec, obj, obj_name, schemas_spec)
            if result is not None:
                return result

    if "oneOf" in spec:
        found_valid = False
        for one_spec in spec.get("oneOf", []):
            result = validate_object_spec(one_spec, obj, obj_name, schemas_spec)
            if result is None:
                if found_valid:
                    return f"{obj_name} matches more than one of the given 'oneOf' definitions: {spec.get('oneOf', [])}"
                found_valid = True
        if not found_valid:
            return f"{obj_name} does not match any of of the given 'oneOf' definitions: {spec.get('oneOf', [])}"

    if "anyOf" in spec:
        found_valid = False
        for any_spec in spec.get("anyOf", []):
            result = validate_object_spec(any_spec, obj, obj_name, schemas_spec)
            if result is None:
                found_valid = True
                break
        if not found_valid:
            return f"{obj_name} does not match any of of the given 'anyOf' definitions: {spec.get('anyOf', [])}"

    if spec.get("type", "") == "object":
        if type(obj) is not dict:
            return f"{obj_name} must be an object"

        for required_field in spec.get("required", []):
            if required_field not in obj:
                return f"{obj_name} missing required field {required_field}"

        for prop, p_spec in spec.get("properties", {}).items():
            if prop in obj:
                result = validate_object_spec(p_spec, obj[prop], obj_name + "." + prop, schemas_spec)
                if result is not None:
                    return result
    if spec.get("properties", ""):
        for prop, p_spec in spec.get("properties", {}).items():
            value = obj.get(prop)
            if '$ref' in p_spec:
                p_spec = get_ref_from_spec(schemas_spec,p_spec['$ref'])
            if prop in obj:
                result = validate_object_spec(p_spec, obj[prop], obj_name + "." + prop, schemas_spec)
                if result is not None:
                    return result
    elif spec.get("type", "") == "array":
        if type(obj) is not list:
            return f"{obj_name} must be an array"

        idx = 0
        for item in obj:
            result = validate_object_spec(spec.get("items", {}), item, obj_name + ".items." + str(idx), schemas_spec)
            if result is not None:
                return result
            idx += 1
    elif spec.get("type", "") == "integer":
        if type(obj) is not int:
            return f"{obj_name} must be an integer"

        if "minimum" in spec:
            if spec["minimum"] > obj:
                return f"{obj_name} is less than the minimum of {spec['minimum']}"
        if "maximum" in spec:
            if spec["maximum"] < obj:
                return f"{obj_name} is greater than the maximum of {spec['maximum']}"
    elif spec.get("type", "") == "string":
        if type(obj) is not str:
            return f"{obj_name} must be a string"

        if "enum" in spec:
            if obj not in spec["enum"]:
                return f"{obj_name} must be one of {spec['enum']}"

        if "minLength" in spec:
            if spec["minLength"] > len(obj):
                return f"{obj_name} is shorter than the minimum length of {spec['minLength']}"
        if "maxLength" in spec:
            if spec["maxLength"] < len(obj):
                return f"{obj_name} is longer than the maximum length of {spec['maxLength']}"

        if "format" in spec:
            if spec["format"] == "ipv4":
                try:
                    ipaddress.ip_address(obj)
                except ValueError:
                    return f"{obj_name} must be in ipv4 format"

    return None

def find_last_json_with_tag(tag):
    last_json = None
    last_file = None
    # Get the current working directory
    directory = os.getcwd()
    # List all files in the directory
    for filename in os.listdir(directory):
        if filename.endswith('.json'):
            filepath = os.path.join(directory, filename)
            # Open and load the JSON file
            with open(filepath, 'r') as f:
                try:
                    data = json.load(f)
                    # Check if the tag exists in the JSON data
                    if tag in data:
                        last_json = data
                        last_file = filename
                except json.JSONDecodeError:
                    print(f"Error decoding JSON in {filename}")
    return last_file