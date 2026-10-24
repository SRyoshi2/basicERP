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
export type ContactImportRow = {
  row_number: number;
  display_name: string;
  data: ContactInput;
  errors: Record<string, string[]>;
};
export type ContactImportBatch = Omit<components["schemas"]["ContactImportBatch"], "rows" | "result"> & {
  rows: ContactImportRow[];
  result: { contacts?: Array<{ id: string; customer_number: string }> };
};
export type ContactActivity = Required<components["schemas"]["ContactActivity"]>;
export type ContactActivityInput = Pick<
  ContactActivity,
  "contact" | "kind" | "subject" | "body" | "occurred_at"
>;
export type ContactActivityPage = Omit<
  components["schemas"]["PaginatedContactActivityList"],
  "results"
> & { results: ContactActivity[] };
export type CatalogPriceInput = Omit<components["schemas"]["CatalogPrice"], "id">;
export type CatalogItem = Required<components["schemas"]["CatalogItem"]> & {
  current_price: components["schemas"]["CatalogPrice"] | null;
};
export type CatalogItemInput = Omit<components["schemas"]["CatalogItemCreate"], "prices"> & {
  prices: CatalogPriceInput[];
};
export type CatalogPage = Omit<components["schemas"]["PaginatedCatalogItemList"], "results"> & {
  results: CatalogItem[];
};
export type InvoiceValidationError = { code: string; field?: string; message: string };
export type InvoiceValidationReport = {
  validator: string;
  scope: string;
  passed: boolean;
  errors: InvoiceValidationError[];
  xml_root?: string;
  detected_xml_format?: string;
  embedded_xml_sha256?: string;
};
export type IncomingInvoice = Omit<components["schemas"]["IncomingInvoice"], "validation_report"> & {
  validation_report: InvoiceValidationReport;
};
export type IncomingInvoicePage = Omit<
  components["schemas"]["PaginatedIncomingInvoiceList"],
  "results"
> & { results: IncomingInvoice[] };
export type Project = Required<components["schemas"]["Project"]>;
export type ProjectInput = components["schemas"]["ProjectCreate"];
export type ProjectPage = Omit<components["schemas"]["PaginatedProjectList"], "results"> & {
  results: Project[];
};
export type AssigneeOption = components["schemas"]["AssigneeOption"];
export type WorkPackage = Required<components["schemas"]["WorkPackage"]>;
export type WorkPackageInput = components["schemas"]["WorkPackageCreate"];
export type WorkPackagePage = Omit<
  components["schemas"]["PaginatedWorkPackageList"], "results"
> & { results: WorkPackage[] };
export type ProjectControlling = components["schemas"]["ProjectControlling"];
export type TimeEntry = Required<components["schemas"]["TimeEntry"]>;
export type TimeEntryInput = components["schemas"]["TimeEntryCreate"];
export type TimeEntryPage = Omit<components["schemas"]["PaginatedTimeEntryList"], "results"> & {
  results: TimeEntry[];
};
export type ServiceEntry = Required<components["schemas"]["ServiceEntry"]>;
export type ServiceEntryInput = components["schemas"]["ServiceEntryCreate"];
export type ServiceEntryPage = Omit<
  components["schemas"]["PaginatedServiceEntryList"], "results"
> & { results: ServiceEntry[] };
export type ProjectTimeSummary = components["schemas"]["ProjectTimeSummary"];
export type TimeReport = components["schemas"]["TimeReport"];
export type TimeReportFilters = {
  dateFrom: string;
  dateTo: string;
  project?: string;
  employee?: string;
};
export type AbsenceRequest = Required<components["schemas"]["AbsenceRequest"]>;
export type AbsenceInput = components["schemas"]["AbsenceCreate"];
export type AbsencePage = Omit<
  components["schemas"]["PaginatedAbsenceRequestList"], "results"
> & { results: AbsenceRequest[] };
export type LeaveBalance = components["schemas"]["LeaveBalance"];
export type LeaveEntitlement = components["schemas"]["LeaveEntitlement"];
export type ManualIncomingInvoiceInput = {
  invoice_number: string;
  issue_date: string;
  seller_name: string;
  buyer_name: string;
  currency: string;
  payable_amount: string;
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

export async function previewContactImport(file: File): Promise<ContactImportBatch> {
  const data = new FormData();
  data.append("file", file);
  return request<ContactImportBatch>("/api/v1/crm/imports/preview/", {
    method: "POST",
    body: data,
  });
}

export async function applyContactImport(batch: ContactImportBatch): Promise<ContactImportBatch> {
  return request<ContactImportBatch>(`/api/v1/crm/imports/${batch.id}/apply/`, {
    method: "POST",
    body: "{}",
  });
}

export async function getContactActivities(contactId: string): Promise<ContactActivityPage> {
  return request<ContactActivityPage>(`/api/v1/crm/activities/?contact=${encodeURIComponent(contactId)}`);
}

export async function createContactActivity(data: ContactActivityInput): Promise<ContactActivity> {
  return request<ContactActivity>("/api/v1/crm/activities/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateContactActivity(
  activity: ContactActivity,
  data: ContactActivityInput,
): Promise<ContactActivity> {
  return request<ContactActivity>(`/api/v1/crm/activities/${activity.id}/`, {
    method: "PATCH",
    body: JSON.stringify({ ...data, version: activity.version }),
  });
}

export async function archiveContactActivity(activity: ContactActivity): Promise<ContactActivity> {
  return request<ContactActivity>(`/api/v1/crm/activities/${activity.id}/archive/`, {
    method: "POST",
    body: "{}",
  });
}

export async function getCatalogItems(options: {
  search?: string;
  kind?: "product" | "service" | "";
  unit?: "hour" | "day" | "piece" | "flat" | "";
  page?: number;
} = {}): Promise<CatalogPage> {
  const params = new URLSearchParams();
  if (options.search) params.set("search", options.search);
  if (options.kind) params.set("kind", options.kind);
  if (options.unit) params.set("unit", options.unit);
  if (options.page && options.page > 1) params.set("page", String(options.page));
  const query = params.size ? `?${params.toString()}` : "";
  return request<CatalogPage>(`/api/v1/catalog/items/${query}`);
}

export async function createCatalogItem(data: CatalogItemInput): Promise<CatalogItem> {
  return request<CatalogItem>("/api/v1/catalog/items/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateCatalogItem(item: CatalogItem, data: CatalogItemInput): Promise<CatalogItem> {
  return request<CatalogItem>(`/api/v1/catalog/items/${item.id}/`, {
    method: "PATCH",
    body: JSON.stringify({ ...data, version: item.version }),
  });
}

export async function archiveCatalogItem(item: CatalogItem): Promise<CatalogItem> {
  return request<CatalogItem>(`/api/v1/catalog/items/${item.id}/archive/`, {
    method: "POST",
    body: "{}",
  });
}

export async function getProjects(options: {
  search?: string;
  status?: "quotation" | "active" | "paused" | "completed" | "";
  page?: number;
} = {}): Promise<ProjectPage> {
  const params = new URLSearchParams();
  if (options.search) params.set("search", options.search);
  if (options.status) params.set("status", options.status);
  if (options.page && options.page > 1) params.set("page", String(options.page));
  const query = params.size ? `?${params.toString()}` : "";
  return request<ProjectPage>(`/api/v1/projects/${query}`);
}

export async function createProject(data: ProjectInput): Promise<Project> {
  return request<Project>("/api/v1/projects/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateProject(project: Project, data: ProjectInput): Promise<Project> {
  return request<Project>(`/api/v1/projects/${project.id}/`, {
    method: "PATCH",
    body: JSON.stringify({ ...data, version: project.version }),
  });
}

export async function archiveProject(project: Project): Promise<Project> {
  return request<Project>(`/api/v1/projects/${project.id}/archive/`, {
    method: "POST",
    body: "{}",
  });
}

export async function getProjectControlling(projectId: string): Promise<ProjectControlling> {
  return request<ProjectControlling>(`/api/v1/projects/${projectId}/controlling/`);
}

export async function getProjectAssignees(): Promise<AssigneeOption[]> {
  return request<AssigneeOption[]>("/api/v1/projects/assignees/");
}

export async function getWorkPackages(projectId: string): Promise<WorkPackagePage> {
  const params = new URLSearchParams({ project: projectId });
  return request<WorkPackagePage>(`/api/v1/projects/work-packages/?${params.toString()}`);
}

export async function createWorkPackage(data: WorkPackageInput): Promise<WorkPackage> {
  return request<WorkPackage>("/api/v1/projects/work-packages/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateWorkPackage(
  workPackage: WorkPackage,
  data: WorkPackageInput,
): Promise<WorkPackage> {
  return request<WorkPackage>(`/api/v1/projects/work-packages/${workPackage.id}/`, {
    method: "PATCH",
    body: JSON.stringify({ ...data, version: workPackage.version }),
  });
}

export async function archiveWorkPackage(workPackage: WorkPackage): Promise<WorkPackage> {
  return request<WorkPackage>(`/api/v1/projects/work-packages/${workPackage.id}/archive/`, {
    method: "POST",
    body: "{}",
  });
}

export async function getTimeEntries(options: {
  dateFrom?: string;
  dateTo?: string;
  project?: string;
  employee?: string;
  page?: number;
} = {}): Promise<TimeEntryPage> {
  const params = new URLSearchParams();
  if (options.dateFrom) params.set("date_from", options.dateFrom);
  if (options.dateTo) params.set("date_to", options.dateTo);
  if (options.project) params.set("project", options.project);
  if (options.employee) params.set("employee", options.employee);
  if (options.page && options.page > 1) params.set("page", String(options.page));
  const query = params.size ? `?${params.toString()}` : "";
  return request<TimeEntryPage>(`/api/v1/time/entries/${query}`);
}

export async function createTimeEntry(data: TimeEntryInput): Promise<TimeEntry> {
  return request<TimeEntry>("/api/v1/time/entries/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateTimeEntry(entry: TimeEntry, data: TimeEntryInput): Promise<TimeEntry> {
  return request<TimeEntry>(`/api/v1/time/entries/${entry.id}/`, {
    method: "PATCH",
    body: JSON.stringify({ ...data, version: entry.version }),
  });
}

export async function archiveTimeEntry(entry: TimeEntry): Promise<TimeEntry> {
  return request<TimeEntry>(`/api/v1/time/entries/${entry.id}/archive/`, {
    method: "POST",
    body: "{}",
  });
}

export async function getServiceEntries(options: {
  dateFrom?: string;
  dateTo?: string;
  project?: string;
  employee?: string;
  page?: number;
} = {}): Promise<ServiceEntryPage> {
  const params = new URLSearchParams();
  if (options.dateFrom) params.set("date_from", options.dateFrom);
  if (options.dateTo) params.set("date_to", options.dateTo);
  if (options.project) params.set("project", options.project);
  if (options.employee) params.set("employee", options.employee);
  if (options.page && options.page > 1) params.set("page", String(options.page));
  const query = params.size ? `?${params.toString()}` : "";
  return request<ServiceEntryPage>(`/api/v1/time/service-entries/${query}`);
}

export async function createServiceEntry(data: ServiceEntryInput): Promise<ServiceEntry> {
  return request<ServiceEntry>("/api/v1/time/service-entries/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateServiceEntry(
  entry: ServiceEntry,
  data: ServiceEntryInput,
): Promise<ServiceEntry> {
  return request<ServiceEntry>(`/api/v1/time/service-entries/${entry.id}/`, {
    method: "PATCH",
    body: JSON.stringify({ ...data, version: entry.version }),
  });
}

export async function archiveServiceEntry(entry: ServiceEntry): Promise<ServiceEntry> {
  return request<ServiceEntry>(`/api/v1/time/service-entries/${entry.id}/archive/`, {
    method: "POST",
    body: "{}",
  });
}

export async function getProjectTimeSummary(projectId: string): Promise<ProjectTimeSummary> {
  const params = new URLSearchParams({ project: projectId });
  return request<ProjectTimeSummary>(`/api/v1/time/project-summary/?${params.toString()}`);
}

function timeReportQuery(options: TimeReportFilters): string {
  const params = new URLSearchParams({ date_from: options.dateFrom, date_to: options.dateTo });
  if (options.project) params.set("project", options.project);
  if (options.employee) params.set("employee", options.employee);
  return params.toString();
}

export async function getTimeReport(options: TimeReportFilters): Promise<TimeReport> {
  return request<TimeReport>(`/api/v1/time/report/?${timeReportQuery(options)}`);
}

export function timeReportExportUrl(options: TimeReportFilters): string {
  return `/api/v1/time/report/export/?${timeReportQuery(options)}`;
}

export async function getAbsences(options: {
  year?: number;
  status?: "requested" | "approved" | "rejected" | "cancelled" | "";
  employee?: string;
} = {}): Promise<AbsencePage> {
  const params = new URLSearchParams();
  if (options.year) params.set("year", String(options.year));
  if (options.status) params.set("status", options.status);
  if (options.employee) params.set("employee", options.employee);
  const query = params.size ? `?${params.toString()}` : "";
  return request<AbsencePage>(`/api/v1/hr/absences/${query}`);
}

export async function createAbsence(data: AbsenceInput): Promise<AbsenceRequest> {
  return request<AbsenceRequest>("/api/v1/hr/absences/", {
    method: "POST", body: JSON.stringify(data),
  });
}

export async function updateAbsence(
  absence: AbsenceRequest, data: AbsenceInput,
): Promise<AbsenceRequest> {
  return request<AbsenceRequest>(`/api/v1/hr/absences/${absence.id}/`, {
    method: "PATCH", body: JSON.stringify({ ...data, version: absence.version }),
  });
}

export async function cancelAbsence(absence: AbsenceRequest): Promise<AbsenceRequest> {
  return request<AbsenceRequest>(`/api/v1/hr/absences/${absence.id}/cancel/`, {
    method: "POST", body: "{}",
  });
}

export async function reviewAbsence(
  absence: AbsenceRequest, decision: "approved" | "rejected", decisionNote = "",
): Promise<AbsenceRequest> {
  return request<AbsenceRequest>(`/api/v1/hr/absences/${absence.id}/review/`, {
    method: "POST", body: JSON.stringify({ decision, decision_note: decisionNote }),
  });
}

export async function getLeaveBalance(
  year: number, employee?: string,
): Promise<LeaveBalance> {
  const params = new URLSearchParams({ year: String(year) });
  if (employee) params.set("employee", employee);
  return request<LeaveBalance>(`/api/v1/hr/leave-balance/?${params.toString()}`);
}

export async function setLeaveEntitlement(data: {
  employee: string;
  year: number;
  entitlement_days: string;
  carryover_days: string;
  version?: number | null;
}): Promise<LeaveEntitlement> {
  return request<LeaveEntitlement>("/api/v1/hr/leave-entitlements/", {
    method: "POST", body: JSON.stringify(data),
  });
}

export async function getIncomingInvoices(options: {
  search?: string;
  status?: "valid" | "invalid" | "";
  format?: "standard_pdf" | "xrechnung_ubl" | "xrechnung_cii" | "zugferd" | "unknown" | "";
  page?: number;
} = {}): Promise<IncomingInvoicePage> {
  const params = new URLSearchParams();
  if (options.search) params.set("search", options.search);
  if (options.status) params.set("status", options.status);
  if (options.format) params.set("format", options.format);
  if (options.page && options.page > 1) params.set("page", String(options.page));
  const query = params.size ? `?${params.toString()}` : "";
  return request<IncomingInvoicePage>(`/api/v1/archive/incoming-invoices/${query}`);
}

export async function uploadIncomingInvoice(
  file: File,
  manual?: ManualIncomingInvoiceInput,
): Promise<IncomingInvoice> {
  const data = new FormData();
  data.append("file", file);
  data.append("mode", manual ? "standard_pdf" : "automatic");
  if (manual) {
    for (const [key, value] of Object.entries(manual)) data.append(key, value);
  }
  return request<IncomingInvoice>("/api/v1/archive/incoming-invoices/", {
    method: "POST",
    body: data,
  });
}
