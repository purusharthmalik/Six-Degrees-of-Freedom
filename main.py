from dotenv import load_dotenv
from langchain_huggingface import HuggingFaceEmbeddings
import numpy as np
from connect_to_neo import Neo4jDB
from wiki_scraper import scrape
from sklearn.metrics.pairwise import cosine_similarity
import concurrent.futures
from collections import deque

load_dotenv()

# Caching the embeddings to avoid redundant LLM calls
embed_cache = {}

def get_embedding(page, llm):
    if page not in embed_cache:
        embed_cache[page] = llm.embed_query(page)
    return embed_cache[page]

def heuristic(current_page, end_page, llm):
    current_embed = get_embedding(current_page, llm)
    end_embed = get_embedding(end_page, llm)
    
    current_embed = np.array(current_embed).reshape(1, -1)
    end_embed = np.array(end_embed).reshape(1, -1)
    
    return 1 - cosine_similarity(current_embed, end_embed)[0][0]

def parallel_scrape_and_store(page, db_connection):
    # Scrape the page for hyperlinks
    neighbors = scrape(page)
    # Batch create nodes and links in Neo4j
    db_connection.create_page(page)
    with db_connection.driver.session() as session:
        with session.begin_transaction() as tx:
            for neighbor in neighbors:
                db_connection._create_page_node(tx, neighbor)
                db_connection._create_link(tx, page, neighbor)
    return neighbors

def search(entity_one, entity_two, db_connection, llm, max_depth=6, top_n_neighbors=10):
    def dfs(current_page, end_page, depth, path, visited):
        if depth > max_depth:
            return None
        
        visited.add(current_page)
        path.append(current_page)

        if current_page == end_page:
            return path

        # Scrape and store the neighbors of the current page using parallel processing
        with concurrent.futures.ThreadPoolExecutor() as executor:
            neighbors = executor.submit(parallel_scrape_and_store, current_page, db_connection).result()
        
        # Fetch neighbors from the database
        neighbors_from_db = db_connection.get_links(current_page)
        if not neighbors_from_db:
            path.pop()
            visited.remove(current_page)
            return None
        
        # Cache embeddings to reduce redundant calls
        neighbors_with_similarity = []
        end_embed = get_embedding(end_page, llm)

        for neighbor in neighbors_from_db:
            try:
                neighbor_embed = get_embedding(neighbor, llm)
                similarity = cosine_similarity([neighbor_embed], [end_embed])[0][0]
                neighbors_with_similarity.append((neighbor, similarity))
            except Exception as e:
                print(f"Error getting embedding for {neighbor}: {e}")

        # Sort neighbors based on similarity and limit to top N
        sorted_neighbors = [n for n, _ in sorted(neighbors_with_similarity, key=lambda x: x[1], reverse=True)[:top_n_neighbors]]

        # Traverse each sorted neighbor
        for neighbor in sorted_neighbors:
            print(f"Going through the page for {neighbor}")
            if neighbor not in visited:
                result = dfs(neighbor, end_page, depth + 1, path, visited)
                if result:
                    return result
        
        path.pop()
        visited.remove(current_page)
        return None

    # Initial scrape and store for the start entity
    links = parallel_scrape_and_store(entity_one, db_connection)

    # Perform DFS from the starting entity
    visited = set()
    path = []
    result = dfs(entity_one, entity_two, 0, path, visited)
    return result

def main():
    DB_CONNECTION = Neo4jDB("bolt://localhost:7687", "neo4j", "sixdegrees")
    LLM = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    print("Model loaded!")

    entity_one = input("Enter the start point: ").strip().replace(" ", "_")
    entity_two = input("Enter the end point: ").strip().replace(" ", "_")
    
    path = search(entity_one, entity_two, DB_CONNECTION, LLM)

    if path:
        print(f'Found a path in {len(path)-1} steps!')
        print(' -> '.join(path))
    else:
        print('No path found within the step limit.') 

if __name__ == "__main__":
    main()