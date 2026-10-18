const API_URL =
  import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

const USER_ID_KEY = "memeit_user_id";

export type RecommendationResponse = {
  type: "trending" | "personalized";
  generation_count: number;
  next_unlock?: number;
  cached?: boolean;
  themes: string[];
  trending_themes: string[];
  personalized_themes: string[];
};

export type ThemeEvent = {
  user_id: string;
  theme: string;
  custom_theme: string;
  action: "generated" | "selected" | "sticker_created" | "downloaded";
};

export function getUserId(): string {
  let userId = localStorage.getItem(USER_ID_KEY);

  if (!userId) {
    userId = crypto.randomUUID();
    localStorage.setItem(USER_ID_KEY, userId);
  }

  return userId;
}

async function readResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let message = `Request failed (${response.status})`;

    try {
      const data: unknown = await response.json();
      if (
        typeof data === "object" &&
        data !== null &&
        "detail" in data &&
        typeof data.detail === "string"
      ) {
        message = data.detail;
      }
    } catch {
      // Keep the default message.
    }

    throw new Error(message);
  }

  return (await response.json()) as T;
}

export async function registerAnonymousUser(userId: string): Promise<void> {
  const response = await fetch(
    `${API_URL}/api/users/${encodeURIComponent(userId)}`,
    { method: "POST" }
  );
  await readResponse<unknown>(response);
}

export async function fetchRecommendations(
  userId: string,
  refresh = false
): Promise<RecommendationResponse> {
  const params = new URLSearchParams();
  if (refresh) params.set("refresh", "true");
  const query = params.toString();

  const response = await fetch(
    `${API_URL}/api/ai-theme-recommendations/${encodeURIComponent(userId)}${query ? `?${query}` : ""}`,
    { method: "GET", cache: "no-store" }
  );

  return readResponse<RecommendationResponse>(response);
}

export async function recordThemeGeneration(
  userId: string,
  theme: string,
  customTheme: string
): Promise<void> {
  const event: ThemeEvent = {
    user_id: userId,
    theme,
    custom_theme: theme === "Custom Theme" ? customTheme.trim() : "",
    action: "generated",
  };

  const response = await fetch(`${API_URL}/api/theme-event`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(event),
  });

  await readResponse<unknown>(response);
}

export async function saveGeneratedMemes(
  userId: string,
  theme: string,
  customTheme: string,
  memes: {
    caption: string;
    characters: { person_index: number; label: string }[];
  }[]
): Promise<string[]> {
  const response = await fetch(`${API_URL}/api/generated-memes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user_id: userId,
      theme,
      custom_theme: theme === "Custom Theme" ? customTheme.trim() : "",
      caption_style: "mixed",
      memes,
    }),
  });

  const data = await readResponse<{
    saved: boolean;
    memes: { id: string }[];
  }>(response);

  return data.memes.map((meme) => meme.id);
}

export async function recordMemeFeedback(
  userId: string,
  memeId: string,
  action: "selected" | "liked" | "disliked" | "sticker_created"
): Promise<void> {
  const response = await fetch(`${API_URL}/api/meme-feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId, meme_id: memeId, action }),
  });

  await readResponse<unknown>(response);
}
