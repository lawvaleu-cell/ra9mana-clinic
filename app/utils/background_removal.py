"""
Suppression automatique d'arrière-plan pour logos, signatures et cachets.

Aucun modèle d'IA n'est utilisé ici (pas d'accès réseau pour télécharger des
poids de modèle dans cet environnement) : la méthode est heuristique et
fonctionne bien pour des images avec un fond uni ou quasi uni (blanc, gris
clair, etc.), ce qui couvre la grande majorité des logos, signatures et
cachets scannés ou photographiés sur feuille blanche.
"""
from PIL import Image


def remove_background(input_path, output_path, tolerance=28):
    """
    Rend transparent le fond uni d'une image (détecté depuis les coins).
    Sauvegarde le résultat en PNG (avec canal alpha) à output_path.
    Retourne True si un fond a été détecté et supprimé, False sinon.
    """
    img = Image.open(input_path).convert("RGBA")
    width, height = img.size
    pixels = img.load()

    # Échantillonne les 4 coins pour deviner la couleur de fond
    corners = [(0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1)]
    corner_colors = [pixels[x, y][:3] for x, y in corners]

    # Si les coins ne sont pas cohérents entre eux, on ne devine pas de fond
    def close(c1, c2, tol=18):
        return all(abs(a - b) <= tol for a, b in zip(c1, c2))

    reference = corner_colors[0]
    if not all(close(reference, c) for c in corner_colors[1:]):
        return False

    def is_background(pixel_rgb):
        return all(abs(int(pixel_rgb[i]) - int(reference[i])) <= tolerance for i in range(3))

    new_pixels = img.getdata()
    result = []
    for p in new_pixels:
        if is_background(p[:3]):
            result.append((p[0], p[1], p[2], 0))
        else:
            result.append(p)

    img.putdata(result)
    img.save(output_path, "PNG")
    return True
