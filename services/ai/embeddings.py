import numpy as np
import faiss

def generate_embeddings(model, text):
    return model.encode([text])[0]

def create_faiss_index(embeddings_dict:dict):
    if not embeddings_dict:
        raise ValueError("Cannot create FAISS index: embeddings_dict is empty")
    dimension = next(iter(embeddings_dict.values())).shape[0]
    index = faiss.IndexFlatL2(dimension)
    vectors = np.array(list(embeddings_dict.values()))
    index.add(vectors)
    return index

def similarity_search(model, query, embeddings, k=2):
    query_embedding = generate_embeddings(model, query)
    index = create_faiss_index(embeddings)
    distances, indices = index.search(np.array([query_embedding]), k)
    policy_names = list(embeddings.keys())
    return [policy_names[i] for i in indices[0]]

