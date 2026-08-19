import asyncio
import os
import random
import time

from playwright.async_api import async_playwright

import config
from scraper import selectors

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/151.0.0.0 Safari/537.36"
)


class ScraperError(Exception):
    pass


class LoginRequiredError(ScraperError):
    pass


class CaptchaError(ScraperError):
    pass


class LushaScraper:

    def scrape(self, company, progress, max_pages, departments=None, seniorities=None, countries=None):
        return asyncio.run(
            self._scrape(company, progress, max_pages, departments, seniorities, countries)
        )

    def login(self, timeout_seconds=None):
        return asyncio.run(self._login(timeout_seconds or config.LOGIN_TIMEOUT_SECONDS))

    async def _scrape(self, company, progress, max_pages, departments=None, seniorities=None, countries=None):
        browser, context, page = await self._open()
        try:
            all_results = []
            page_no = 0
            while True:
                page_no += 1
                if max_pages > 0 and page_no > max_pages:
                    break
                if max_pages <= 0 and page_no > config.ALL_PAGES_SAFETY_LIMIT:
                    break

                if page_no == 1:
                    await page.goto(
                        config.LUSHA_PROSPECTING_URL,
                        wait_until="domcontentloaded",
                        timeout=60000,
                    )
                    await self._check_interruptions(page)
                    await self._human_delay(2, 3)
                    await self._search(page, company)
                    await self._apply_departments(page, departments)
                    await self._apply_seniorities(page, seniorities)
                    await self._apply_countries(page, countries)
                else:
                    await self._human_delay(1, 2)
                    await self._goto_next_page(page)

                await self._wait_for_results(page)
                await self._check_interruptions(page)

                page_results = await self._extract_results(page)
                new_on_page = self._new_items(page_results, all_results)
                all_results.extend(new_on_page)

                progress(page_no, len(all_results), all_results)

                if not page_results or not new_on_page:
                    break
                if not await self._has_next(page):
                    break
                await self._human_delay(
                    config.PAGE_DELAY_MIN, config.PAGE_DELAY_MAX
                )
            try:
                await context.storage_state(path=config.STORAGE_STATE_PATH)
            except Exception:
                pass
            return all_results
        finally:
            await browser.close()
            await self._pw.stop()

    async def _search(self, page, company):
        await self._check_interruptions(page)
        box = page.locator(selectors.SEARCH_INPUT).first
        if await box.count() == 0:
            box = page.locator(selectors.SEARCH_INPUT_FALLBACK).first
        try:
            await box.fill(company, timeout=10000)
            await page.wait_for_timeout(1200)
            await box.press("Enter", timeout=10000)
            await page.wait_for_timeout(1500)
        except Exception:
            await self._check_interruptions(page)
            raise

    @staticmethod
    def _known_map(known):
        return {value.strip().lower(): value.strip() for value in known}

    def _selected_values(self, raw, known_map, label):
        raw = [
            str(value).strip()
            for value in raw
            if value and str(value).strip()
        ]
        selected = []
        for value in dict.fromkeys(raw):
            key = value.lower()
            if key in known_map:
                selected.append(known_map[key])
            else:
                print(f"AVISO: {label} no reconocido por Lusha, se omite:", value)
        if not selected:
            raise ScraperError(
                f"Ninguno de los {label} indicados es válido para Lusha."
            )
        return selected

    async def _expand_filter(self, page, group_selector):
        group = page.locator(group_selector).first
        if await group.count() == 0:
            raise ScraperError("No se encontró el filtro.")
        # Si el panel ya está abierto (su contenido es visible) no se clica:
        # el clic en el centro de un panel abierto cae sobre chips/input y
        # Lusha añade filtros extra (departamento/nivel no pedidos).
        open_hint = None
        for hint in (
            selectors.DEPARTMENT_INPUT,
            selectors.SENIORITY_CHECKBOX,
            selectors.LOCATION_INPUT,
        ):
            probe = group.locator(hint).first
            if await probe.count() > 0:
                try:
                    if await probe.is_visible():
                        open_hint = hint
                        break
                except Exception:
                    pass
        if open_hint is None:
            try:
                await group.scroll_into_view_if_needed()
            except Exception:
                pass
            await group.click(timeout=10000)
            await page.wait_for_timeout(800)
        return group

    async def _collapse_filter(self, page, group_selector):
        # Escape cierra el dropdown sin clicar el centro del panel, que podía
        # aterrizar sobre una chip/input y añadir filtros extra.
        try:
            await page.keyboard.press("Escape")
        except Exception:
            pass
        await page.wait_for_timeout(1500)

    async def _apply_departments(self, page, departments):
        if not departments:
            return
        await self._check_interruptions(page)
        known = self._known_map(selectors.KNOWN_DEPARTMENTS)
        selected = self._selected_values(departments, known, "departamento")
        group = await self._expand_filter(page, selectors.DEPARTMENT_FILTER)

        chips = group.locator(selectors.DEPARTMENT_CHIP)

        async def current_names():
            # Los chips seleccionados exponen su nombre en `data-for="tooltip-<X>"`.
            names = set()
            count = await chips.count()
            for index in range(count):
                tip = await chips.nth(index).get_attribute("data-for") or ""
                if tip.startswith("tooltip-"):
                    names.add(tip[len("tooltip-"):].strip())
            return names

        async def click_option(dept):
            box = page.locator(selectors.DEPARTMENT_INPUT).first
            try:
                await box.wait_for(state="visible", timeout=10000)
            except Exception:
                raise ScraperError(
                    "No se encontró el buscador del filtro de departamento."
                )
            await box.click(timeout=10000)
            await box.fill(dept, timeout=10000)
            # Espera de estabilización: sin ella, clicar durante el render listo
            # del dropdown disparaba puntualmente una selección extra.
            await page.wait_for_timeout(1200)
            option = group.get_by_text(dept, exact=True).last
            try:
                await option.wait_for(state="visible", timeout=10000)
            except Exception:
                print("AVISO: no se encontró la opción de departamento:", dept)
                return False
            await option.scroll_into_view_if_needed()
            await option.click(timeout=10000)
            await page.wait_for_timeout(2500)
            return True

        # Selección autoverificada: reintenta los faltantes y retira los chips
        # no pedidos (p.ej. un departamento extra añadido por la carrera).
        for _ in range(3):
            current = await current_names()
            missing = {dept for dept in selected if dept not in current}
            extra = {name for name in current if name not in selected}
            if not missing and not extra:
                break

            for dept in sorted(missing):
                await click_option(dept)

            for name in sorted(extra):
                chip = None
                count = await chips.count()
                for index in range(count):
                    tip = await chips.nth(index).get_attribute("data-for") or ""
                    if tip == "tooltip-" + name:
                        chip = chips.nth(index)
                        break
                if chip is None:
                    continue
                try:
                    await chip.locator("#svg-container").first.click(timeout=10000)
                except Exception:
                    print("AVISO: no se pudo retirar el departamento extra:", name)
                    continue
                await page.wait_for_timeout(2500)

        leftover = await current_names()
        for name in sorted(leftover):
            if name not in selected:
                print("AVISO: no se pudo retirar el departamento extra:", name)

        await self._collapse_filter(page, selectors.DEPARTMENT_FILTER)

    async def _apply_seniorities(self, page, seniorities):
        if not seniorities:
            return
        await self._check_interruptions(page)
        known = self._known_map(selectors.KNOWN_SENIORITIES)
        selected = self._selected_values(seniorities, known, "nivel de seniority")
        group = await self._expand_filter(page, selectors.SENIORITY_FILTER)

        # El filtro de seniority es una lista de checkboxes (no input de búsqueda).
        # Tras una búsqueda Lusha pone la etiqueta en title-case y le añade el
        # conteo de población (p.ej. "C-Suite 2.6K"), así que se compara en
        # minúsculas contra la etiqueta normalizada de cada fila.
        wanted = {value.lower() for value in selected}
        matched = set()
        items = group.locator(selectors.SENIORITY_CHECKBOX)
        try:
            await items.first.wait_for(state="visible", timeout=10000)
        except Exception:
            pass

        count = await items.count()
        for index in range(count):
            item = items.nth(index)
            try:
                label = (await item.locator('[class*="TextContainer"]').first.inner_text()).strip().lower()
            except Exception:
                continue
            if label not in wanted or label in matched:
                continue
            await item.scroll_into_view_if_needed()
            await item.click(timeout=10000)
            matched.add(label)
            # Cada selección dispara la búsqueda automáticamente.
            await page.wait_for_timeout(2500)
            if matched == wanted:
                break

        for level in selected:
            if level.lower() not in matched:
                print("AVISO: no se encontró la opción de seniority:", level)

        await self._collapse_filter(page, selectors.SENIORITY_FILTER)

    async def _apply_countries(self, page, countries):
        if not countries:
            return
        await self._check_interruptions(page)
        group = await self._expand_filter(page, selectors.LOCATION_FILTER)

        for country in [str(value).strip() for value in countries if value]:
            box = page.locator(selectors.LOCATION_INPUT).first
            try:
                await box.wait_for(state="visible", timeout=10000)
            except Exception:
                raise ScraperError(
                    "No se encontró el buscador del filtro de ubicación."
                )
            await box.click(timeout=10000)
            await box.fill(country, timeout=10000)
            # Deja que el dropdown filtre antes de buscar la opción exacta.
            await page.wait_for_timeout(1200)
            option = None
            opts = group.locator(selectors.LOCATION_OPTION)
            count = await opts.count()
            for index in range(count):
                try:
                    text = (await opts.nth(index).inner_text()).strip()
                except Exception:
                    continue
                if text.lower() == country.lower():
                    option = opts.nth(index)
                    break
            if option is None:
                print("AVISO: no se encontró la opción de país:", country)
                continue
            await option.scroll_into_view_if_needed()
            await option.click(timeout=10000)
            # Cada país seleccionado dispara la búsqueda automáticamente.
            await page.wait_for_timeout(4000)

        await self._collapse_filter(page, selectors.LOCATION_FILTER)

    async def _wait_for_results(self, page):
        deadline = time.time() + 25
        while time.time() < deadline:
            count = await page.locator(selectors.RESULT_ROW).count()
            if count > 0:
                await page.wait_for_timeout(2000)
                return
            await asyncio.sleep(config.RESULT_WAIT_SECONDS)
        await page.wait_for_timeout(2000)

    async def _goto_next_page(self, page):
        await self._check_interruptions(page)
        next_btn = page.locator(selectors.NEXT_PAGE).first
        if await next_btn.count() == 0:
            raise ScraperError("No se encontró el botón de página siguiente.")
        try:
            await next_btn.click(timeout=10000)
        except Exception:
            await self._check_interruptions(page)
            raise

    @staticmethod
    async def _has_next(page):
        next_btn = page.locator(selectors.NEXT_PAGE).first
        if await next_btn.count() == 0:
            return False
        try:
            disabled = await next_btn.get_attribute("disabled")
            if disabled is not None:
                return False
            aria = await next_btn.get_attribute("aria-disabled")
            if aria == "true":
                return False
        except Exception:
            pass
        return True

    async def _extract_results(self, page):
        results = []
        rows = page.locator(selectors.RESULT_ROW)
        count = await rows.count()
        for index in range(count):
            row = rows.nth(index)
            name = ""
            try:
                text = (await row.inner_text()).strip()
                name = text.splitlines()[0].strip() if text else ""
            except Exception:
                name = ""
            role = ""
            title = row.locator(selectors.JOB_TITLE)
            if await title.count() > 0:
                try:
                    role = (await title.first.inner_text()).strip()
                except Exception:
                    role = ""
            url = ""
            linkedin = row.locator(selectors.LINKEDIN_LINK)
            if await linkedin.count() > 0:
                try:
                    url = await linkedin.first.get_attribute("href")
                    url = url.split("?")[0] if url else ""
                except Exception:
                    url = ""
            if not name and not url:
                continue
            results.append({"name": name, "role": role, "url": url})
        return results

    @staticmethod
    def _new_items(page_results, accumulated):
        keys = {
            row.get("url") or (row.get("name") + "|" + row.get("role"))
            for row in accumulated
        }
        return [
            row
            for row in page_results
            if (row.get("url") or (row.get("name") + "|" + row.get("role"))) not in keys
        ]

    async def _check_interruptions(self, page):
        url = page.url.lower()
        if any(mark in url for mark in selectors.CAPTCHA_URL_MARKS):
            raise CaptchaError("Lusha mostró un CAPTCHA o challenge.")
        if any(mark in url for mark in selectors.AUTH_URL_MARKS):
            raise LoginRequiredError("Lusha redirigió a la pantalla de inicio de sesión.")

    async def _open(self):
        self._pw = await async_playwright().start()
        browser = await self._pw.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--start-maximized",
            ],
            ignore_default_args=["--enable-automation"],
        )
        context = await browser.new_context(
            storage_state=config.STORAGE_STATE_PATH
            if os.path.exists(config.STORAGE_STATE_PATH)
            else None,
            user_agent=USER_AGENT,
            viewport={"width": 1366, "height": 900},
            locale="es-ES",
            timezone_id="America/Mexico_City",
        )
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        page = await context.new_page()
        return browser, context, page

    @staticmethod
    async def _has_valid_session(page):
        if "auth.lusha.com" in page.url.lower():
            return False
        try:
            return await page.locator(selectors.FILTER_PANEL).count() > 0
        except Exception:
            return False

    async def _login(self, timeout_seconds):
        browser, context, page = await self._open()
        try:
            await page.goto(
                config.LUSHA_DASHBOARD_URL,
                wait_until="domcontentloaded",
                timeout=60000,
            )
            await page.wait_for_timeout(3000)
            if "auth.lusha.com" not in page.url.lower():
                await page.goto(
                    config.LUSHA_PROSPECTING_URL,
                    wait_until="domcontentloaded",
                    timeout=60000,
                )
                await page.wait_for_timeout(3000)

            if not await self._has_valid_session(page):
                print(
                    "Inicia sesión en la ventana del navegador "
                    "(correo + contraseña o SSO)."
                )
                deadline = time.time() + timeout_seconds
                while time.time() < deadline:
                    if await self._has_valid_session(page):
                        break
                    if "auth.lusha.com" not in page.url.lower():
                        await page.goto(
                            config.LUSHA_PROSPECTING_URL,
                            wait_until="domcontentloaded",
                            timeout=60000,
                        )
                    await asyncio.sleep(config.LOGIN_POLL_SECONDS)
                if not await self._has_valid_session(page):
                    raise ScraperError(
                        "Tiempo agotado para completar el inicio de sesión."
                    )
            await self._save_state(context)
            return "login_completado"
        finally:
            await browser.close()
            await self._pw.stop()

    @staticmethod
    async def _save_state(context):
        await context.storage_state(path=config.STORAGE_STATE_PATH)

    async def _human_delay(self, lo=1.5, hi=3.5):
        await asyncio.sleep(random.uniform(lo, hi))