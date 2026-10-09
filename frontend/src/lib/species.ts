import type { Case } from "../api/cases";

/** Indian zebu (humped) cattle breeds — Bos indicus. */
const INDICINE = ["gir", "sahiwal", "red sindhi", "tharparkar", "ongole", "kankrej", "hariana", "rathi", "deoni", "kangayam", "hallikar", "amrit mahal", "vechur", "punganur"];

/** Latin binomial for the specimen plate, from species and breed. Crossbreds of exotic dairy breeds
 *  with zebu stock are written as the cross. */
export function latinName(c: Pick<Case, "species" | "signalment">): string {
  const breed = c.signalment.breed.toLowerCase();
  switch (c.species) {
    case "dog":
      return "Canis lupus familiaris";
    case "cat":
      return "Felis catus";
    case "buffalo":
      return "Bubalus bubalis";
    case "goat":
      return "Capra hircus";
    case "sheep":
      return "Ovis aries";
    case "poultry":
      return "Gallus gallus domesticus";
    case "cattle":
      if (INDICINE.some((b) => breed.includes(b))) return "Bos indicus";
      if (breed.includes("cross")) return "Bos taurus × Bos indicus";
      return "Bos taurus";
  }
}

