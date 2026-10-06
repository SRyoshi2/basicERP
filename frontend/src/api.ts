import type { components } from "./generated/api-schema";

export type User = components["schemas"]["User"];
export type CompanyProfile = Required<
  Omit<components["schemas"]["CompanyProfile"], "logo">
>;
export type Contact = Required<components["schemas"]["Contact"]>;
export type ContactAddressInput = Omit<components["schemas"]["Address"], "id">;
export type ContactPersonInput = Omit<components["schemas"]["ContactPerson"], "id">;
export type ContactInput = Omit<
  components["schemas"]["ContactCreate"],
  "addresses" | "contact_persons"
> & {
  addresses: ContactAddressInput[];
  contact_persons: ContactPersonInput[];
};
export type ContactPage = Omit<components["schemas"]["PaginatedContactList"], "results"> & {
  results: Contact[];
};

type ErrorBody = {
  error?: components["schemas"]["ApiError"];
  detail?: string;
  [key: string]: unknown;
};

function firstMessage(value: unknown): string | null {
  if (typeof value === "string") return value;
  if (Array.isArray(value)) {
    for (const item of value) {
      const message = firstMessage(item);
      if (message) return message;
    }
  }
  if (value && typeof value === "object") {
    for (const item of Object.values(value)) {
      const message = firstMessage(item);
      if (message) return message;
    }
  }
  return null;
}

function csrfToken(): string {
  const entry = document.cookie
    .split(";")
    .map((item) => item.trim())
    .find((item) => item.startsWith("csrftoken="));
  return entry ? decodeURIComponent(entry.split("=").slice(1).join("=")) : "";
}

async function request<T>(url: string, init: RequestInit = {}): Promise<T> {
  const isFormData = init.body instanceof FormData;
  const response = await fetch(url, {
    ...init,
    credentials: "same-origin",
    headers: {
      ...(!isFormData ? { "Content-Type": "application/json" } : {}),
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
    const message = firstMessage(body.error?.fields) ?? body.error?.message ?? body.detail;
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

export async function getCompanyProfile(): Promise<CompanyProfile> {
  return request<CompanyProfile>("/api/v1/company/");
}

export async function updateCompanyProfile(data: FormData): Promise<CompanyProfile> {
  return request<CompanyProfile>("/api/v1/company/", {
    method: "PATCH",
    body: data,
  });
}

export async function getContacts(options: {
  search?: string;
  kind?: "organization" | "person" | "";
  page?: number;
} = {}): Promise<ContactPage> {
  const params = new URLSearchParams();
  if (options.search) params.set("search", options.search);
  if (options.kind) params.set("kind", options.kind);
  if (options.page && options.page > 1) params.set("page", String(options.page));
  const query = params.size ? `?${params.toString()}` : "";
  return request<ContactPage>(`/api/v1/crm/contacts/${query}`);
}

export async function createContact(data: ContactInput): Promise<Contact> {
  return request<Contact>("/api/v1/crm/contacts/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateContact(contact: Contact, data: ContactInput): Promise<Contact> {
  return request<Contact>(`/api/v1/crm/contacts/${contact.id}/`, {
    method: "PATCH",
    body: JSON.stringify({ ...data, version: contact.version }),
  });
}

export async function archiveContact(contact: Contact): Promise<Contact> {
  return request<Contact>(`/api/v1/crm/contacts/${contact.id}/archive/`, {
    method: "POST",
    body: "{}",
  });
}
