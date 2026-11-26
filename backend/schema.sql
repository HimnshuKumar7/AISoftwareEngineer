-- AI Software Engineer: PostgreSQL schema (Neon). Generated from app/db/models.py via
--   python -m app.scripts.export_schema
-- The API also creates these tables on startup when AUTO_CREATE_TABLES=true (default).

CREATE TABLE IF NOT EXISTS users (
	id UUID NOT NULL, 
	email VARCHAR(320) NOT NULL, 
	name VARCHAR(120), 
	password_hash VARCHAR(128) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id)
);

CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users (email);

CREATE TABLE IF NOT EXISTS repositories (
	id UUID NOT NULL, 
	user_id UUID NOT NULL, 
	url VARCHAR(500) NOT NULL, 
	owner VARCHAR(100) NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	branch VARCHAR(120), 
	commit_sha VARCHAR(40), 
	status VARCHAR(20) NOT NULL, 
	status_message TEXT, 
	progress INTEGER NOT NULL, 
	file_count INTEGER NOT NULL, 
	chunk_count INTEGER NOT NULL, 
	languages JSON NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	indexed_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_repo_per_user UNIQUE (user_id, owner, name), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_repositories_status ON repositories (status);
CREATE INDEX IF NOT EXISTS ix_repositories_user_created ON repositories (user_id, created_at);
CREATE INDEX IF NOT EXISTS ix_repositories_user_id ON repositories (user_id);

CREATE TABLE IF NOT EXISTS query_history (
	id UUID NOT NULL, 
	user_id UUID NOT NULL, 
	repo_id UUID NOT NULL, 
	conversation_id UUID NOT NULL, 
	mode VARCHAR(20) NOT NULL, 
	question TEXT NOT NULL, 
	answer TEXT NOT NULL, 
	sub_queries JSON NOT NULL, 
	sources JSON NOT NULL, 
	citations JSON NOT NULL, 
	llm_provider VARCHAR(20), 
	llm_model VARCHAR(120), 
	latency_ms INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(repo_id) REFERENCES repositories (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_query_history_conversation_id ON query_history (conversation_id);
CREATE INDEX IF NOT EXISTS ix_query_history_repo_conv ON query_history (repo_id, conversation_id, created_at);
CREATE INDEX IF NOT EXISTS ix_query_history_user_id ON query_history (user_id);

CREATE TABLE IF NOT EXISTS repo_indexes (
	repo_id UUID NOT NULL, 
	faiss_blob BYTEA NOT NULL, 
	chunks_blob BYTEA NOT NULL, 
	chunk_count INTEGER NOT NULL, 
	embedding_model VARCHAR(120) NOT NULL, 
	dim INTEGER NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (repo_id), 
	FOREIGN KEY(repo_id) REFERENCES repositories (id) ON DELETE CASCADE
);


