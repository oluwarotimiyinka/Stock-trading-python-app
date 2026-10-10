from importlib.metadata import distribution

d = distribution("snowflake-connector-python")
for req in d.metadata.get_all("Requires-Dist", []):
    if "pandas" in req.lower() or "pyarrow" in req.lower():
        print(req)
