import { useEffect, useState } from "react";
import {
  fetchRecommendations,
  getUserId,
  registerAnonymousUser,
  type RecommendationResponse,
} from "./recommendations";

type Props = {
  onSelectTheme: (theme: string) => void;
  generationVersion: number;
  disabled?: boolean;
};

export default function ThemeRecommendations({
  onSelectTheme,
  generationVersion,
  disabled = false,
}: Props) {
  const [recommendations, setRecommendations] = useState<RecommendationResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError("");
      try {
        const userId = getUserId();
        await registerAnonymousUser(userId);
        const data = await fetchRecommendations(userId);
        if (!cancelled) setRecommendations(data);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load recommendations.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => { cancelled = true; };
  }, [generationVersion]);

  async function newIdeas() {
    if (disabled || refreshing) return;
    setRefreshing(true);
    setError("");
    try {
      const data = await fetchRecommendations(getUserId(), true);
      setRecommendations(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not refresh suggestions.");
    } finally {
      setRefreshing(false);
    }
  }

  function renderTopics(topics: string[]) {
    return (
      <div className="meme-theme-grid">
        {topics.map((topic, index) => (
          <button
            key={`${topic}-${index}`}
            type="button"
            className="meme-theme-button"
            disabled={disabled || loading || refreshing}
            onClick={() => onSelectTheme(topic)}
            title={`Use ${topic} as your meme theme`}
          >
            {topic}
          </button>
        ))}
      </div>
    );
  }

  const trending = recommendations?.trending_themes ?? [];
  const personalized = recommendations?.personalized_themes ?? [];
  const remaining = recommendations?.next_unlock ?? 0;

  return (
    <div style={{ marginTop: 24, marginBottom: 24, display: "grid", gap: 18 }}>
      {loading && <p role="status">Loading meme topics...</p>}
      {error && <p className="error-message" role="alert">{error}</p>}

      {!loading && (
        <>
          <section style={{ padding: 20, border: "1px solid rgba(128,128,128,0.3)", borderRadius: 16 }}>
            <h3 style={{ marginTop: 0 }}>🔥 Trending on Meme-it</h3>
            <p style={{ opacity: 0.75 }}>Popular meme topics across Meme-it.</p>
            {trending.length > 0 ? renderTopics(trending) : <p>No trending topics yet.</p>}
          </section>

          <section style={{ padding: 20, border: "1px solid rgba(128,128,128,0.3)", borderRadius: 16 }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
              <h3 style={{ margin: 0 }}>✨ Suggested for You</h3>
              {personalized.length > 0 && (
                <button type="button" className="meme-theme-button" disabled={disabled || refreshing} onClick={() => void newIdeas()}>
                  {refreshing ? "Refreshing..." : "↻ New ideas"}
                </button>
              )}
            </div>
            {personalized.length > 0 ? (
              <>
                <p style={{ opacity: 0.75 }}>AI-recommended topics based on your meme interests.</p>
                {renderTopics(personalized)}
              </>
            ) : remaining > 0 ? (
              <p style={{ opacity: 0.75 }}>
                Generate memes {remaining} more {remaining === 1 ? "time" : "times"} to unlock personalized AI topics.
              </p>
            ) : (
              <p>Personalized topics are not available yet.</p>
            )}
          </section>
        </>
      )}
    </div>
  );
}
