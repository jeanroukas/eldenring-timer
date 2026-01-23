import winsdk
import inspect

def explore(module, path, depth=0):
    if depth > 4: return
    for name in dir(module):
        if name.startswith("_"): continue
        try:
            val = getattr(module, name)
            new_path = f"{path}.{name}"
            # Check for our target functions
            if "CreateDirect3D11Device" in name or "create_direct3d11_device" in name.lower():
                print(f"FOUND: {new_path}")
            
            if inspect.ismodule(val) or type(val).__name__ == "module":
                if "winsdk" in str(val):
                    explore(val, new_path, depth+1)
        except: pass

print("Scanning winsdk...")
explore(winsdk, "winsdk")
print("Scan complete.")
