from neo4j import GraphDatabase

class Neo4jDB:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        try:
            self.driver.verify_connectivity()
            print("Connection established!")
        except Exception as e:
            print(f"Error connecting to the database: {e}")

    def close(self):
        self.driver.close()

    def create_page(self, title):
        with self.driver.session() as session:
            session.write_transaction(self._create_page_node, title)

    @staticmethod
    def _create_page_node(tx, title):
        query = """
        MERGE (p:Page {title: $title})
        RETURN p
        """
        tx.run(query, title=title)

    def create_link(self, start_title, end_title):
        with self.driver.session() as session:
            session.write_transaction(self._create_link, start_title, end_title)

    @staticmethod
    def _create_link(tx, start_title, end_title):
        query = """
        MATCH (start:Page {title: $start_title})
        MERGE (end:Page {title: $end_title})
        MERGE (start)-[:LINKS_TO]->(end)
        """
        tx.run(query, start_title=start_title, end_title=end_title)

    def get_links(self, title):
        with self.driver.session() as session:
            return session.read_transaction(self._get_links, title)

    @staticmethod
    def _get_links(tx, title):
        query = """
        MATCH (start:Page {title: $title})-[:LINKS_TO]->(end:Page)
        RETURN end.title AS end_title
        """
        result = tx.run(query, title=title)
        return [record['end_title'] for record in result]
