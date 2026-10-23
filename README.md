# Núcleo

Centro de sistema gráfico y elegante (PySide6 / Qt6) para Arch y CachyOS.
Reúne las tareas de mantenimiento más habituales de `pacman` en una interfaz
clara, con consola interactiva, historial de la sesión y avisos de progreso.

## Funciones

| Página | Qué hace |
| --- | --- |
| **Panel general** | Resumen con tiles animados (actualizaciones, huérfanas, caché, disco, paquetes, servicios fallidos), info del equipo y asistente de **mantenimiento completo** por pasos. |
| **Actualizar** | Modo seguro: comprueba bloqueo, espacio, base de datos, keyring, snapshot y noticias; si hay un aviso crítico (intervención manual, keyring roto, poco espacio) **aborta**. Crea un snapshot y actualiza **solo repositorios** con `pacman -Syu`. El **AUR se revisa y actualiza aparte** con «Revisar AUR», nunca en automático. Al terminar avisa si hay que reiniciar (kernel, systemd, glibc, NVIDIA o Mesa) y ofrece huérfanas/caché. |
| **Paquetes** | Búsqueda local y remota, instalación, eliminación y búsqueda/instalación de paquetes de AUR con `paru`. La actualización masiva de AUR se hace desde Actualizar > Revisar AUR. |
| **Huérfanas** | Lista las dependencias sin usar (`pacman -Qdtq`), muestra su tamaño y las elimina con `pacman -Rns`. |
| **Caché** | Estadísticas de `/var/cache/pacman/pkg` (tamaño y número de paquetes), selección granular y limpieza con `paccache`. |
| **Limpieza** | Papelera, miniaturas/cachés de usuario, registros de `journald` y log de pacman. |
| **Snapshots** | Instantáneas de `snapper` (config `root`): crear, eliminar y `cleanup`. |
| **Espejos** | Estado de la mirrorlist y optimización con `reflector` (país, protocolo, número, frescura, orden por velocidad). |
| **Historial** | Todos los comandos ejecutados en la sesión con su salida y resultado. |

## Requisitos

- Python 3.11 o superior (probado con 3.14).
- PySide6.
- Utilidades opcionales: `pacman-contrib` (para `paccache` y `checkupdates`),
  `reflector`, `snapper`, `paru` y `polkit`.
- `sudo` en funcionamiento. La contraseña se pide una sola vez y se cachea el
  *timestamp* de `sudo`, por lo que conviene un `timestamp_timeout` razonable.

## Instalación y ejecución

```bash
cd ~/Apps/Nucleo
./install.sh   # crea el venv, instala dependencias e instala el icono y la entrada de menú
./run.sh
```

`install.sh` genera `~/.local/share/applications/nucleo.desktop` con las rutas
reales del proyecto, así que la app queda disponible en el menú de aplicaciones.

## Estructura

```
Nucleo/
├── main.py               # punto de entrada (QApplication + ventana)
├── run.sh                # lanzador
├── install.sh            # crea el venv e instala icono y entrada de menú
├── core/                 # capa de datos y ejecución
│   ├── proc.py           # ejecución asíncrona (QThreadPool) y entorno LC_ALL=C
│   ├── runner.py         # CommandRunner / SequenceRunner sobre QProcess
│   ├── auth.py           # validación y caché de sudo
│   ├── queries.py        # consultas a pacman/paru/snapper/reflector
│   ├── system.py         # información del sistema
│   ├── session.py        # registro del historial de la sesión
│   └── util.py           # formateo de tamaños, tiempos y duraciones
├── ui/
│   ├── theme.py          # paleta, fuentes y hoja de estilo (QSS)
│   ├── icons.py          # iconos SVG en línea
│   ├── responsive.py     # contenedores dinámicos y texto con elide
│   ├── window.py         # ventana principal, barra lateral y navegación
│   ├── components/       # widgets reutilizables, diálogos y toasts
│   └── pages/            # una vista por tarea
└── assets/               # icono de la aplicación y knobs de los interruptores
```

## Notas

- La interfaz es fluida: usa contenedores dinámicos (`ResponsiveGrid`, `FlowLayout`,
  `WrapRow`) en lugar de posiciones fijas. Las tarjetas y tiles se reordenan según
  el ancho disponible, y las barras de acciones se envuelven a varias filas.
- La barra lateral cambia a modo compacto (solo iconos) por debajo de 900 px, por
  lo que la app se ve bien tanto a pantalla completa como en una ventana pequeña.
- Los textos largos se recortan con puntos suspensivos (`ElidedLabel`, equivalente
  a `elide: Text.ElideRight`) y muestran el texto completo en el tooltip.
- La consola se puede desplazar, contraer y abrir en una ventana grande desde sus
  botones de cabecera; la tabla y la consola de la página de actualización están
  separadas por un divisor ajustable.
- El modo seguro de actualización y el mantenimiento completo aplican las mismas
  comprobaciones y crean un snapshot con `snapper` antes de tocar pacman. `snap-pac` sigue creando sus snapshots pre/post y `grub-btrfs` permite
  arrancar una instantánea anterior si algo va mal.
- Las noticias de Arch/CachyOS se leen desde la última actualización completa; una
  noticia de intervención manual bloquea la actualización y se muestra el enlace.
- El AUR nunca se actualiza con el botón principal. «Revisar AUR» muestra los
  paquetes, avisa de `-git`/Caelestia/Quickshell y crea otro snapshot antes de
  ejecutar `paru`.
- Los controles importantes incluyen tooltips que explican qué comando ejecutan o
  qué efecto tienen.
- Todas las consultas se ejecutan con `LC_ALL=C` para poder analizar la salida
  de las herramientas en inglés con independencia del idioma del sistema.
- Los comandos privilegiados se ejecutan como `sudo <programa> <args>` con listas
  de argumentos (nunca a través de un shell), de modo que la contraseña nunca se
  filtra al `stdin` de `pacman`.
- Los comandos se registran en el historial de la sesión (salida truncada para
  no consumir memoria).
