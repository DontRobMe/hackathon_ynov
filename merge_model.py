from peft import AutoPeftModelForCausalLM
from transformers import AutoTokenizer

adapter_path = r"C:\Users\Administrateur\projet\hackathon_ynov\models\phi3_financial"
output_path = r"C:\Users\Administrateur\projet\hackathon_ynov\models\phi3_financial_merged"

print("Loading model + adapter...")
model = AutoPeftModelForCausalLM.from_pretrained(adapter_path, device_map="cpu")
tokenizer = AutoTokenizer.from_pretrained("microsoft/Phi-3-mini-4k-instruct")

print("Merging...")
model.merge_and_unload()

print("Saving merged model...")
model.save_pretrained(output_path)
tokenizer.save_pretrained(output_path)
print(f"✓ Merged model at {output_path}")
