import en from "../../app_faces/locales/en.json";
import zh from "../../app_faces/locales/zh.json";
import hi from "../../app_faces/locales/hi.json";
import es from "../../app_faces/locales/es.json";
import fr from "../../app_faces/locales/fr.json";
import ar from "../../app_faces/locales/ar.json";
import bn from "../../app_faces/locales/bn.json";
import pt from "../../app_faces/locales/pt.json";
import ru from "../../app_faces/locales/ru.json";
import ur from "../../app_faces/locales/ur.json";

export const catalogs: Record<string, Record<string, string>> = {
  en,
  zh,
  hi,
  es,
  fr,
  ar,
  bn,
  pt,
  ru,
  ur,
};
let selected = "en";

export function negotiate(preferences: readonly string[]): string {
  for (const preference of preferences) {
    const base = preference.toLowerCase().replaceAll("_", "-").split("-")[0];
    if (base && Object.hasOwn(catalogs, base)) return base;
  }
  return "en";
}

export function locale(): string {
  return selected;
}

export function t(
  message: string,
  values: Record<string, string | number> = {},
): string {
  const active: Record<string, string> = catalogs[selected] ?? en;
  const text = Object.hasOwn(active, message)
    ? (active[message] ?? message)
    : message;
  return text.replace(/\{(\w+)\}/g, (placeholder: string, key: string) =>
    Object.hasOwn(values, key) ? String(values[key]) : placeholder,
  );
}

export function initializeLanguage(): void {
  selected = negotiate(navigator.languages);
  const textNodes: Array<[Text, string]> = [];
  const attributes: Array<[Element, string, string]> = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    if (node.parentElement?.closest("script, style")) continue;
    const source = (node.textContent ?? "").replace(/\s+/g, " ").trim();
    if (Object.hasOwn(en, source)) textNodes.push([node as Text, source]);
  }
  for (const element of document.querySelectorAll(
    "[aria-label], [placeholder]",
  )) {
    for (const name of ["aria-label", "placeholder"]) {
      const source = element.getAttribute(name);
      if (source && Object.hasOwn(en, source))
        attributes.push([element, name, source]);
    }
  }
  document.documentElement.lang = selected;
  document.documentElement.dir = ["ar", "ur"].includes(selected)
    ? "rtl"
    : "ltr";
  document.title = t("App Faces · Moderation");
  for (const [node, source] of textNodes) node.textContent = t(source);
  for (const [element, name, source] of attributes)
    element.setAttribute(name, t(source));
}
