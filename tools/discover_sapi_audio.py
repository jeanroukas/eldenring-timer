import pyttsx3
import comtypes.client

def list_sapi_outputs():
    try:
        # Standard SAPI5 SpVoice
        speaker = comtypes.client.CreateObject("SAPI.SpVoice")
        outputs = speaker.GetAudioOutputs()
        print(f"Count: {outputs.Count}")
        for i in range(outputs.Count):
            item = outputs.Item(i)
            desc = item.GetDescription()
            id = item.Id
            print(f"Index {i}: {desc} | ID: {id}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    list_sapi_outputs()
