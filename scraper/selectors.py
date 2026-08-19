# Selectores del dashboard de Lusha (dashboard.lusha.com), verificados en vivo (2026).
# Se resuelven por atributos data-test-id (estables); las clases `sc-*` cambian entre builds.

# Input de búsqueda de contactos (prospecting). Clases: `peer l:mr-sm ...` (fallback).
SEARCH_INPUT = '[data-test-id="prospecting-free-text-search"]'
SEARCH_INPUT_FALLBACK = "input.peer"

# Panel lateral de filtros: señal de que la sesión es válida en /prospecting/contacts.
FILTER_PANEL = '[data-test-id="filter-panel-wrapper"]'

# Cada fila de contacto: el div con data-test-id="contacts-table-contact-name-N".
RESULT_ROW = '[data-test-id^="contacts-table-contact-name-"]'

# Cargo dentro de la fila: data-test-id="job-title-N".
JOB_TITLE = '[data-test-id^="job-title-"]'

# URL de LinkedIn dentro de la fila.
LINKEDIN_LINK = 'a[href*="linkedin.com/in/"]'

# Paginación (Material-UI): botones next/previous; se deshabilitan al llegar al final.
NEXT_PAGE = '[data-test-id="pagination-next-page"]'
PREV_PAGE = '[data-test-id="pagination-previous-page"]'

# Filtro de departamento (grupo acordeón + input de búsqueda de opciones).
# Cada departamento seleccionado aparece como chip con el nombre en el atributo
# `data-for="tooltip-<Dept>"` y un botón de borrado con id `svg-container`.
DEPARTMENT_FILTER = '[data-test-id="contactDepartment-filter"]'
DEPARTMENT_INPUT = '[data-test-id="contactDepartment-filter-input"]'
DEPARTMENT_CHIP = '[data-test-id^="contactDepartment-chip-"]'

# Filtro de seniority (grupo acordeón con lista de checkboxes, sin input de búsqueda).
# Cada fila es un checkbox; la etiqueta está en una span con clase *TextContainer*
# y va en title-case con un conteo de población (p.ej. "C-Suite 2.6K").
SENIORITY_FILTER = '[data-test-id="contactSeniority-filter"]'
SENIORITY_CHECKBOX = '[data-test-id^="checkbox-contactSeniority-"]'

# Filtro de ubicación de contactos (país, en este proyecto solo país).
# Es un grupo acordeón con input de búsqueda (`contactLocation-filter-input`):
# teclear un país muestra opciones `contactLocation-option-N` con texto exacto y,
# al hacer clic en la correcta, la búsqueda se dispara automáticamente (cambia el
# requestId). El botón "Apply" del pie solo aplica la sección ZIP/rango, no la
# ubicación.
LOCATION_FILTER = '[data-test-id="contactLocation-filter"]'
LOCATION_INPUT = '[data-test-id="contactLocation-filter-input"]'
LOCATION_OPTION = '[data-test-id^="contactLocation-option-"]'

# Departamentos disponibles en el filtro de Lusha (verificados en vivo, 2026).
# Se usan para validar la entrada del usuario y para sugerencias en el frontend.
KNOWN_DEPARTMENTS = [
    "Engineering & Technical",
    "Business Development",
    "Consulting",
    "Customer Service",
    "Finance",
    "General Management",
    "Health Care & Medical",
    "Human Resources",
    "Information Technology",
    "Legal",
    "Marketing",
    "Operations",
    "Product",
    "Research & Analytics",
    "Sales",
]

# Niveles de seniority disponibles en el filtro de Lusha (verificados en vivo, 2026).
# Se usan para validar la entrada del usuario y para sugerencias en el frontend.
KNOWN_SENIORITIES = [
    "Founder",
    "Partner",
    "C-suite",
    "Vice president",
    "Director",
    "Manager",
    "Senior",
    "Entry",
    "Intern",
]

# Marcas de sesión inválida / captcha.
AUTH_URL_MARKS = ("auth.lusha.com", "/login", "/signin")
CAPTCHA_URL_MARKS = ("captcha", "challenge")
