import { useState } from "react";
import { Eye, EyeOff } from "lucide-react";
import IconButton from "../../components/ui/IconButton";
import TextField from "../../components/ui/TextField";

export default function PasswordField(props) {
  const [visible, setVisible] = useState(false);
  return (
    <TextField
      label="Password"
      name="password"
      type={visible ? "text" : "password"}
      enterKeyHint="done"
      trailing={
        <IconButton
          icon={visible ? EyeOff : Eye}
          label={visible ? "Hide password" : "Show password"}
          aria-pressed={visible}
          onClick={() => setVisible((value) => !value)}
        />
      }
      {...props}
    />
  );
}
