export type User = {
  id: string;
  username: string;
  email: string;
  is_staff: boolean;
  must_change_password: boolean;
};

type ErrorBody = {
  detail?: string;
  [key: string]: unknown;
};

function csrfToken(): string {
  const entry = document.cookie
    .split(";")
    .map((item) => item.trim())
    .find((item) => item.startsWith("csrftoken="));
  return entry ? decodeURIComponent(entry.split("=").slice(1).join("=")) : "";
}

async function request<T>(url: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(url, {
    ...init,
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      ...(csrfToken() ? { "X-CSRFToken": csrfToken() } : {}),
      ...init.headers,
    },
  });

  if (!response.ok) {
    let body: ErrorBody = {};
    try {
      body = (await response.json()) as ErrorBody;
    } catch {
      // A proxy failure may not return JSON.
    }
    const fieldMessage = Object.values(body).find((value) => Array.isArray(value));
    const message = body.detail ?? (Array.isArray(fieldMessage) ? String(fieldMessage[0]) : null);
    throw new Error(message ?? `Anfrage fehlgeschlagen (${response.status}).`);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export async function prepareCsrf(): Promise<void> {
  await request<{ csrfToken: string }>("/api/v1/auth/csrf/");
}

export async function currentUser(): Promise<User | null> {
  try {
    return await request<User>("/api/v1/auth/me/");
  } catch {
    return null;
  }
}

export async function signIn(identifier: string, password: string): Promise<User> {
  await prepareCsrf();
  return request<User>("/api/v1/auth/login/", {
    method: "POST",
    body: JSON.stringify({ identifier, password }),
  });
}

export async function signOut(): Promise<void> {
  await request<void>("/api/v1/auth/logout/", { method: "POST", body: "{}" });
}

export async function changePassword(currentPassword: string, newPassword: string): Promise<User> {
  return request<User>("/api/v1/auth/change-password/", {
    method: "POST",
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
  });
}
